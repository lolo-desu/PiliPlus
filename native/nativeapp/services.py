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
        return {**self.item(data), "cid": data["cid"], "pages": data.get("pages", [])}

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
                    "qn": 80,
                    "fnval": 4048,
                },
            )
        else:
            data = self.request(
                "/x/player/wbi/playurl",
                {
                    "bvid": item["id"],
                    "cid": item.get("cid") or detail["cid"],
                    "qn": 80,
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
            video = max(videos, key=lambda v: (v["id"], v.get("bandwidth", 0)))
            audio = max(audios, key=lambda a: a.get("bandwidth", 0)) if audios else None
            return {
                "url": video.get("baseUrl") or video["base_url"],
                "headers": headers,
                "audio": (audio.get("baseUrl") or audio.get("base_url"))
                if audio
                else None,
                "page_url": item["url"],
            }
        streams = data.get("durl") or []
        if len(streams) != 1:
            raise ValueError("当前原生播放器尚未支持此分段响应")
        return {"url": streams[0]["url"], "headers": headers, "page_url": item["url"]}
