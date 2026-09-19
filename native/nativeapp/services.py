"""Native transport adapter for the upstream web API and WBI signing protocol."""

import hashlib
import html
import re
import time
import urllib.parse

APP = "PiliPlus"
API = "https://api.bilibili.com"
# Same permutation as lib/utils/wbi_sign.dart.
MIXIN = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
]


def sign(params, key, timestamp=None):
    values = {**params, "wts": int(time.time()) if timestamp is None else timestamp}
    encoded = "&".join(
        urllib.parse.quote(str(k), safe="")
        + "="
        + urllib.parse.quote(re.sub(r"[!'()*]", "", str(values[k])), safe="")
        for k in sorted(values)
    )
    values["w_rid"] = hashlib.md5((encoded + key).encode()).hexdigest()
    return values


class Service:
    danmaku_segmented = True

    def __init__(self, http, store):
        self.http, self.store = http, store
        self.key = None

    def request(self, path, params=None, wbi=False):
        if wbi:
            if self.key is None:
                nav = self.request("/x/web-interface/nav")
                images = nav["wbi_img"]
                original = "".join(
                    urllib.parse.urlparse(images[k])
                    .path.rsplit("/", 1)[-1]
                    .split(".")[0]
                    for k in ("img_url", "sub_url")
                )
                self.key = "".join(original[i] for i in MIXIN)
            params = sign(params or {}, self.key)
        response = self.http.json(
            API + path,
            query=params,
            headers={
                "Referer": "https://www.bilibili.com/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36",
            },
        )
        # /nav returns useful WBI keys even when the anonymous user is not logged in.
        if response.get("code", 0) and not (
            path.endswith("/nav") and response.get("data", {}).get("wbi_img")
        ):
            raise ValueError(
                f"Bilibili {response['code']}: {response.get('message', '请求失败')}"
            )
        return response.get("data") or response.get("result") or {}

    @staticmethod
    def item(x):
        owner = x.get("owner") or {}
        stat = x.get("stat") or {}
        bvid = x.get("bvid") or str(x.get("aid") or x.get("id"))
        title = html.unescape(re.sub("<[^>]+>", "", x.get("title", "")))
        return {
            "id": bvid,
            "title": title,
            "cover": x.get("pic", ""),
            "subtitle": f"{owner.get('name') or x.get('author', '')} · {stat.get('view') or x.get('play', 0)} 播放",
            "summary": x.get("desc") or x.get("description", ""),
            "url": "https://www.bilibili.com/video/" + bvid,
        }

    def browse(self, page=1):
        return [
            self.item(x)
            for x in self.request("/x/web-interface/popular", {"pn": page, "ps": 30})[
                "list"
            ]
        ]

    def feed(self, mode, page=1):
        if mode == "推荐":
            data = self.request(
                "/x/web-interface/wbi/index/top/feed/rcmd",
                {"ps": 30, "fresh_idx": page, "fresh_type": 3},
                wbi=True,
            )
            return [self.item(x) for x in data.get("item", []) if x.get("bvid")]
        if mode == "排行榜":
            data = self.request(
                "/x/web-interface/ranking/v2", {"rid": 0, "type": "all"}
            )
            return [
                self.item(x) for x in data.get("list", [])[(page - 1) * 30 : page * 30]
            ]
        return self.browse(page)

    def dynamics(self):
        data = self.request("/x/polymer/web-dynamic/v1/feed/all", {"type": "video"})
        result = []
        for item in data.get("items", []):
            major = item.get("modules", {}).get("module_dynamic", {}).get("major") or {}
            archive = major.get("archive")
            if archive:
                result.append(
                    self.item(
                        {
                            **archive,
                            "pic": archive.get("cover", ""),
                            "owner": item.get("modules", {}).get("module_author", {}),
                        }
                    )
                )
        return result

    def search(self, query, page=1):
        result = self.request(
            "/x/web-interface/wbi/search/type",
            {"search_type": "video", "keyword": query, "page": page},
            wbi=True,
        )
        return [self.item(x) for x in result.get("result", [])]

    def calendar(self):
        result = self.request(
            "/pgc/web/timeline", {"types": 1, "before": 3, "after": 3}
        )
        return [
            (
                str(day.get("date", "")),
                [
                    {
                        "id": "ss" + str(x["season_id"]),
                        "title": x["title"],
                        "cover": x.get("cover", ""),
                        "subtitle": x.get("pub_index", ""),
                        "summary": "",
                        "url": x.get("url")
                        or f"https://www.bilibili.com/bangumi/play/ss{x['season_id']}",
                    }
                    for x in day.get("episodes", [])
                ],
            )
            for day in result
        ]

    def detail(self, item):
        if str(item["id"]).startswith("ss"):
            data = self.request(
                "/pgc/view/web/season", {"season_id": str(item["id"])[2:]}
            )
            return {
                **item,
                "summary": data.get("evaluate", ""),
                "episodes": data.get("episodes", []),
            }
        data = self.request("/x/web-interface/wbi/view", {"bvid": item["id"]}, wbi=True)
        return {
            **self.item(data),
            "cid": data["cid"],
            "aid": data["aid"],
            "pages": data.get("pages", []),
        }

    def play(self, item):
        detail = self.detail(item)
        if str(item["id"]).startswith("ss"):
            episode = next(
                (e for e in detail["episodes"] if e.get("id") == item.get("ep_id")),
                detail["episodes"][0],
            )
            data = self.request(
                "/pgc/player/web/playurl",
                {
                    "ep_id": episode["id"],
                    "cid": episode["cid"],
                    "qn": self.store.get("video_quality", 80),
                    "fnval": 4048,
                },
            )
        else:
            data = self.request(
                "/x/player/wbi/playurl",
                {
                    "bvid": item["id"],
                    "cid": item.get("cid") or detail["cid"],
                    "qn": self.store.get("video_quality", 80),
                    "fnval": 4048,
                    "fnver": 0,
                    "fourk": 1,
                },
                wbi=True,
            )
        headers = {"Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0"}
        if data.get("dash"):
            videos = data["dash"]["video"]
            audios = data["dash"].get("audio") or []
            if not videos:
                raise ValueError("未返回可播放的视频流")
            quality = self.store.get("video_quality", 80)
            codec = self.store.get("video_codec", 7)
            eligible = [v for v in videos if v["id"] <= quality] or videos
            video = max(
                eligible,
                key=lambda v: (
                    v["id"],
                    v.get("codecid", 7) == codec,
                    v.get("bandwidth", 0),
                ),
            )
            labels = dict(
                zip(data.get("accept_quality", []), data.get("accept_description", []))
            )
            streams = []
            for stream in sorted(
                videos, key=lambda v: (v["id"], v.get("codecid", 7)), reverse=True
            ):
                code = stream.get("codecid", 7)
                streams.append(
                    {
                        "url": stream.get("baseUrl") or stream["base_url"],
                        "quality": stream["id"],
                        "codec": code,
                        "label": f"{labels.get(stream['id'], str(stream.get('height', stream['id'])) + 'p')} · { {7: 'AVC', 12: 'HEVC', 13: 'AV1'}.get(code, str(code)) }",
                    }
                )
            audio = max(audios, key=lambda a: a.get("bandwidth", 0)) if audios else None
            return {
                "url": video.get("baseUrl") or video["base_url"],
                "headers": headers,
                "audio": (audio.get("baseUrl") or audio.get("base_url"))
                if audio
                else None,
                "page_url": item["url"],
                "streams": streams,
            }
        streams = data.get("durl") or []
        if len(streams) != 1:
            raise ValueError("当前原生播放器尚未支持此分段响应")
        return {"url": streams[0]["url"], "headers": headers, "page_url": item["url"]}

    def qr_generate(self):
        response = self.http.json(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        )
        if response.get("code"):
            raise ValueError(response.get("message", "无法生成二维码"))
        return response["data"]

    def qr_poll(self, key):
        response = self.http.json(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
            query={"qrcode_key": key},
        )
        if response.get("code"):
            raise ValueError(response.get("message", "登录请求失败"))
        data = response["data"]
        if data["code"] == 0:
            account = self.request("/x/web-interface/nav")
            if not account.get("isLogin"):
                raise ValueError("登录响应未建立有效会话")
            self.store.set(
                "bilibili_account",
                {"mid": account["mid"], "name": account.get("uname", "")},
            )
            if data.get("refresh_token"):
                from .credentials import Vault

                Vault(APP, self.store.path).set(
                    "bilibili-refresh", data["refresh_token"]
                )
        # Never pass refresh tokens or cross-domain credential URLs to UI state.
        return {"code": data["code"], "message": data.get("message", "")}

    def logout(self):
        with self.http.lock:
            self.http.cookies.clear()
            self.http.cookies.save(ignore_discard=True)
        self.store.set("bilibili_account", {})
        self.key = None
        from .credentials import Vault

        Vault(APP, self.store.path).remove("bilibili-refresh")

    def danmaku_episodes(self, item):
        detail = self.detail(item)
        if str(item["id"]).startswith("ss"):
            return [
                {"id": e["cid"], "title": e.get("long_title") or e.get("title", "")}
                for e in detail["episodes"]
            ]
        return [{"id": p["cid"], "title": p["part"]} for p in detail["pages"]]

    def danmaku_comments(self, cid, segment=1):
        import base64
        import json
        import os
        from pathlib import Path
        import shlex
        import subprocess
        from .danmaku import Comment

        raw = self.http.request(
            API + "/x/v2/dm/web/seg.so",
            query={"type": 1, "oid": int(cid), "segment_index": segment},
            headers={"Referer": "https://www.bilibili.com/"},
            raw=True,
        )
        binary = Path(__file__).resolve().parents[1] / "bin/pili-core"
        command = shlex.split(os.environ.get("NATIVE_CORE_RUNNER", "")) + [str(binary)]
        result = subprocess.run(
            command,
            input=json.dumps(
                {"method": "danmaku.decode", "data": base64.b64encode(raw).decode()}
            )
            + "\n",
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        value = json.loads(result.stdout)
        if "error" in value:
            raise ValueError(value["error"])
        return [
            Comment(c["time"], c["text"], c["mode"], c["color"])
            for c in value["result"]
            if c["mode"] in (1, 4, 5)
        ]

    def post(self, path, data):
        with self.http.lock:
            csrf = next(
                (
                    cookie.value
                    for cookie in self.http.cookies
                    if cookie.name == "bili_jct"
                    and cookie.domain.lstrip(".") == "bilibili.com"
                ),
                None,
            )
        if not csrf:
            raise ValueError("请先登录 Bilibili")
        response = self.http.json(
            API + path,
            method="POST",
            data={**data, "csrf": csrf},
            json_body=False,
            headers={
                "Referer": "https://www.bilibili.com/",
                "User-Agent": "Mozilla/5.0",
            },
        )
        if response.get("code"):
            raise ValueError(
                f"Bilibili {response['code']}: {response.get('message', '操作失败')}"
            )
        return response.get("data")

    def like(self, item, enabled):
        return self.post(
            "/x/web-interface/archive/like",
            {"bvid": item["id"], "like": 1 if enabled else 2},
        )

    def coin(self, item, count):
        if count not in (1, 2):
            raise ValueError("投币数量无效")
        return self.post(
            "/x/web-interface/coin/add",
            {"bvid": item["id"], "multiply": count, "select_like": 0},
        )

    def favorite_folders(self, item=None):
        account = self.request("/x/web-interface/nav")
        if not account.get("isLogin"):
            raise ValueError("请先登录 Bilibili")
        params = {"up_mid": account["mid"], "type": 2}
        if item:
            params["rid"] = item.get("aid") or self.detail(item)["aid"]
        return self.request("/x/v3/fav/folder/created/list-all", params).get("list", [])

    def favorite_items(self, folder, page=1):
        data = self.request(
            "/x/v3/fav/resource/list",
            {"media_id": folder, "pn": page, "ps": 30, "platform": "web"},
        )
        return [
            self.item(
                {
                    **x,
                    "pic": x.get("cover", ""),
                    "owner": x.get("upper", {}),
                    "stat": x.get("cnt_info", {}),
                }
            )
            for x in data.get("medias", [])
        ]

    def set_favorites(self, item, add, remove):
        aid = item.get("aid") or self.detail(item)["aid"]
        return self.post(
            "/x/v3/fav/resource/deal",
            {
                "rid": aid,
                "type": 2,
                "add_media_ids": ",".join(map(str, add)),
                "del_media_ids": ",".join(map(str, remove)),
            },
        )

    def comments(self, item, page=1):
        aid = item.get("aid") or self.detail(item)["aid"]
        return (
            self.request(
                "/x/v2/reply", {"type": 1, "oid": aid, "pn": page, "ps": 20, "sort": 2}
            ).get("replies", [])
            or []
        )

    def send_comment(self, item, message):
        if not message.strip():
            raise ValueError("评论不能为空")
        aid = item.get("aid") or self.detail(item)["aid"]
        return self.post("/x/v2/reply/add", {"type": 1, "oid": aid, "message": message})
