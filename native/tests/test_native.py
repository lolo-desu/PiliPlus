from pathlib import Path
import sys
import tempfile
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nativeapp.storage import Store
from nativeapp.services import Service, sign
from nativeapp.network import Http


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store("test", self.temp.name)

    def test_export_excludes_credentials_and_round_trips(self):
        self.store.set("theme", "dark")
        self.store.set("cookie", "secret")
        self.store.put("history", {"id": "BVtest", "position": 10})
        data = self.store.export_data()
        self.assertNotIn("cookie", data["settings"])
        self.store.remove("history", "BVtest")
        self.store.import_data(data)
        self.assertEqual(self.store.items("history")[0]["position"], 10)

    def test_invalid_backup_is_atomic(self):
        self.store.set("theme", "light")
        with self.assertRaises(ValueError):
            self.store.import_data(
                {
                    "format": "gnome-media-profile",
                    "version": 1,
                    "settings": {"theme": "dark"},
                    "library": [["bad"]],
                }
            )
        self.assertEqual(self.store.get("theme"), "light")

    def test_wbi_does_not_mutate_request(self):
        original = {"keyword": "中文 & x", "page": 1}
        value = sign(original, "0123456789abcdef", 1234)
        self.assertEqual(value["keyword"], original["keyword"])
        self.assertEqual(value["wts"], 1234)
        self.assertNotIn("wts", original)
        self.assertEqual(
            value, sign({"page": 1, "keyword": "中文 & x"}, "0123456789abcdef", 1234)
        )

    def test_titles_are_plain_text(self):
        item = Service.item(
            {
                "bvid": "BVtest",
                "title": "<em>搜索</em> &amp; 视频",
                "owner": {"name": "UP"},
            }
        )
        self.assertEqual(item["title"], "搜索 & 视频")

    def test_dash_retains_audio_and_selected_page(self):
        service = Service(None, self.store)
        service.detail = lambda item: {"cid": 100}
        called = []

        def request(path, params, wbi):
            called.append(params)
            return {
                "dash": {
                    "video": [
                        {
                            "id": 64,
                            "baseUrl": "https://media.example/video",
                            "bandwidth": 500,
                        }
                    ],
                    "audio": [
                        {"baseUrl": "https://media.example/audio", "bandwidth": 128}
                    ],
                }
            }

        service.request = request
        value = service.play(
            {
                "id": "BVtest",
                "cid": 200,
                "title": "test",
                "url": "https://bilibili.com/video/BVtest",
            }
        )
        self.assertEqual(called[0]["cid"], 200)
        self.assertEqual(value["audio"], "https://media.example/audio")
        self.assertEqual(value["headers"]["Referer"], "https://www.bilibili.com/")

    def test_dash_quality_codec_preference_only_uses_available_streams(self):
        service = Service(None, self.store)
        service.detail = lambda _: {"cid": 100}
        videos = [
            {"id": q, "codecid": c, "baseUrl": f"https://example.com/{q}/{c}"}
            for q, c in [(80, 7), (80, 12), (64, 7), (64, 13)]
        ]
        service.request = lambda *a, **k: {
            "dash": {"video": videos},
            "accept_quality": [80, 64],
            "accept_description": ["1080P", "720P"],
        }
        self.store.set("video_quality", 64)
        self.store.set("video_codec", 13)
        value = service.play(
            {"id": "BVtest", "url": "https://bilibili.com/video/BVtest"}
        )
        self.assertEqual(value["url"], "https://example.com/64/13")
        self.assertEqual(len(value["streams"]), 4)
        self.assertIn("720P · AV1", [s["label"] for s in value["streams"]])
        self.store.set("video_quality", 16)
        self.assertIn(
            service.play({"id": "BVtest", "url": "fixture"})["url"],
            [v["baseUrl"] for v in videos],
        )

    def test_proxy_setting_is_applied_without_replacing_cookie_jar(self):
        http = Http(self.store)
        self.store.set("proxy", "http://127.0.0.1:7890")
        http.set_proxy(self.store.get("proxy"))
        self.assertTrue(
            any(
                isinstance(handler, urllib.request.ProxyHandler)
                for handler in http.opener.handlers
            )
        )
        self.assertIsInstance(
            next(
                handler
                for handler in http.opener.handlers
                if isinstance(handler, urllib.request.HTTPCookieProcessor)
            ),
            urllib.request.HTTPCookieProcessor,
        )
        http.set_proxy("")
        self.assertFalse(
            any(
                isinstance(handler, urllib.request.ProxyHandler)
                for handler in http.opener.handlers
            )
        )

    def test_extended_feature_adapters_normalize_rows(self):
        service = Service(None, self.store)
        responses = {
            "/x/web-interface/search/square": {
                "trending": {"list": [{"keyword": "GTK"}]}
            },
            "/x/web-interface/ranking/v2": {"list": [{"bvid": "BV1", "title": "排行"}]},
            "/x/v2/history/toview/web": {"list": [{"bvid": "BV2", "title": "稍后"}]},
            "/xlive/web-interface/v1/webMain/getMoreRecList": {
                "room_list": [{"roomid": 9, "title": "直播", "uname": "主播"}]
            },
            "/x/web-interface/nav": {"isLogin": True, "mid": 7},
            "/x/relation/followings": {"list": [{"mid": 8, "uname": "关注者"}]},
        }
        service.request = lambda path, params=None, wbi=False: responses[path]
        self.assertEqual(service.hot_keywords()[0]["title"], "GTK")
        self.assertEqual(service.rank()[0]["id"], "BV1")
        self.assertEqual(service.watch_later()[0]["id"], "BV2")
        self.assertEqual(service.live()[0]["live_room_id"], 9)
        self.assertEqual(service.following()[0]["member_id"], 8)

    def test_live_and_account_feature_adapters(self):
        service = Service(None, self.store)
        service.request = lambda path, params=None, wbi=False: {
            "/xlive/web-room/v2/index/getRoomPlayInfo": {
                "playurl_info": {
                    "playurl": {
                        "stream": [
                            {
                                "format": [
                                    {
                                        "codec": [
                                            {
                                                "base_url": "/live.m3u8",
                                                "url_info": [
                                                    {
                                                        "host": "https://cdn.example",
                                                        "extra": "?token=x",
                                                    }
                                                ],
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "/x/web-interface/nav": {"isLogin": True, "mid": 7},
            "/x/web-interface/history/cursor": {
                "list": [{"bvid": "BV3", "title": "历史"}]
            },
            "/x/space/bangumi/follow/list": {
                "list": [{"season_id": 99, "title": "追番"}]
            },
        }[path]
        value = service.live_play(
            {"id": "live:9", "url": "https://live.bilibili.com/9"}
        )
        self.assertEqual(value["url"], "https://cdn.example/live.m3u8?token=x")
        self.assertEqual(service.history_remote()[0]["id"], "BV3")
        self.assertEqual(service.subscriptions()[0]["id"], "ss99")

    def test_member_detail_contains_profile_and_video_rows(self):
        service = Service(None, self.store)
        service.request = lambda path, params=None, wbi=False: {
            "/x/space/wbi/acc/info": {"card": {"name": "UP", "sign": "简介"}},
            "/x/space/wbi/arc/search": {
                "list": {"vlist": [{"bvid": "BV4", "title": "投稿"}]}
            },
        }[path]
        value = service.member_detail({"id": "member:8", "title": "UP"})
        self.assertEqual(value["title"], "UP")
        self.assertEqual(value["videos"][0]["id"], "BV4")

    def test_search_modes_normalize_video_pgc_user_article_and_audio(self):
        service = Service(None, self.store)
        responses = {
            "media_bangumi": [{"season_id": 5, "title": "番剧"}],
            "bili_user": [{"mid": 6, "uname": "用户"}],
            "article": [{"id": 7, "title": "专栏"}],
            "bili_audio": [{"id": 8, "title": "音乐"}],
        }

        def request(path, params=None, wbi=False):
            return {"result": responses[params["search_type"]]}

        service.request = request
        self.assertEqual(service.search_pgc("x")[0]["id"], "ss5")
        self.assertEqual(service.search_users("x")[0]["id"], "member:6")
        self.assertEqual(service.search_articles("x")[0]["id"], "article:7")
        self.assertEqual(service.search_audio("x")[0]["id"], "audio:8")

    def test_api_errors_are_not_empty_success(self):
        class Http:
            def json(self, *args, **kwargs):
                return {"code": -101, "message": "账号未登录"}

        with self.assertRaisesRegex(ValueError, "-101"):
            Service(Http(), self.store).request("/x/example")


if __name__ == "__main__":
    unittest.main()
