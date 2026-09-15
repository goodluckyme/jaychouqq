# -*- coding: utf-8 -*-
"""
肉视频 (rou.video) 爬虫
播放修复：
- 部分片源 CDN 直接返回 #EXTM3U（index.jpg）
- 部分片源返回 PNG，真实 m3u8/TS 藏在自定义 chunk「roUd」里
  · roUd[0]==1 → zlib 解压得到 m3u8
  · roUd[0]==0 → 后接 MPEG-TS
通过 localProxy 解包，避免播放器把 .png/.jpg 当静态图
"""
import sys
import re
import json
import base64
import html as html_lib
import gzip
import zlib
import struct
import ssl
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"
        def getProxyUrl(self, local=True):
            return "http://127.0.0.1:9978/proxy?do=py"


HOST_DEFAULT = "https://rou.video"
FALLBACK_HOSTS = [
    "https://rou.video",
    "https://www.rou.video",
    "https://rouvb1.xyz",
    "https://rouva8.xyz",
    "https://rouva7.xyz",
    "https://rouva5.xyz",
    "https://rouva3.xyz",
]
NAV_URLS = ["https://x99dh.cc", "https://x99dh.one"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

CLASS_LIST = [
    {"type_id": "/v?order=createdAt", "type_name": "🔥 最新发布"},
    {"type_id": "/v?order=viewCount", "type_name": "👑 最多播放"},
    {"type_id": "/v?order=likeCount", "type_name": "❤️ 最受喜爱"},
    {"type_id": "/t/AI短劇", "type_name": "🤖 AI成人短剧"},
    {"type_id": "/t/自拍流出", "type_name": "📱 自拍流出"},
    {"type_id": "/t/探花", "type_name": "🕵️ 探花精选"},
    {"type_id": "/t/國產AV", "type_name": "🇨🇳 国产AV"},
    {"type_id": "/t/日本", "type_name": "🇯🇵 日本精选"},
    {"type_id": "/t/中文字幕", "type_name": "🀄 中文字幕"},
    {"type_id": "/t/麻豆傳媒", "type_name": "麻豆传媒"},
    {"type_id": "/t/糖心Vlog", "type_name": "糖心Vlog"},
    {"type_id": "/t/蜜桃影像傳媒", "type_name": "蜜桃传媒"},
    {"type_id": "/t/香蕉視頻傳媒", "type_name": "香蕉视频"},
    {"type_id": "/t/星空無限傳媒", "type_name": "星空无限"},
    {"type_id": "/t/天美傳媒", "type_name": "天美传媒"},
    {"type_id": "/t/OnlyFans", "type_name": "OnlyFans"},
    {"type_id": "/t/巨乳", "type_name": "巨乳"},
    {"type_id": "/t/人妻", "type_name": "人妻"},
    {"type_id": "/t/絲襪", "type_name": "丝袜"},
    {"type_id": "/t/熟女", "type_name": "熟女"},
    {"type_id": "/t/美少女", "type_name": "美少女"},
    {"type_id": "/t/中出", "type_name": "中出"},
    {"type_id": "/t/口交", "type_name": "口交"},
    {"type_id": "/t/痴女", "type_name": "痴女"},
    {"type_id": "/t/多人運動", "type_name": "多人运动"},
    {"type_id": "/t/NTR", "type_name": "NTR"},
]


class Spider(BaseSpider):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.siteUrl = HOST_DEFAULT
        self._ua = UA
        self.options = {}
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx),
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        cached = None
        try:
            cached = self.getCache("rouav_site")
        except Exception:
            pass
        if cached and str(cached).startswith("http"):
            self.siteUrl = str(cached).rstrip("/")
        else:
            self._refresh_host()
        return True

    def getName(self):
        return "肉视频"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".ts", ".mpd", "/hls/", "index.m3u8", "do=rouhls", "do=routs"))

    def manualVideoCheck(self):
        return False

    # ---------- HTTP ----------
    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self._ua,
            "Referer": referer or (self.siteUrl + "/v"),
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Origin": self.siteUrl,
        }

    def _decode_body(self, raw, enc=""):
        if not raw:
            return b"" if isinstance(raw, (bytes, bytearray)) else ""
        if isinstance(raw, str):
            return raw
        if raw[:2] == b"\x1f\x8b" or enc == "gzip":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return raw

    def _fetch_bytes(self, url, referer=None, timeout=15):
        if url.startswith("/"):
            url = self.siteUrl + url
        req = urllib.request.Request(url, headers=self._headers(referer, accept="*/*"))
        with self.opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding", "")
            raw = self._decode_body(raw, enc)
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="ignore")
            return resp.getcode(), resp.geturl(), raw

    def _fetch(self, url, referer=None, timeout=15, accept=None):
        try:
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = self.siteUrl + url
            req = urllib.request.Request(url, headers=self._headers(referer, accept))
            with self.opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = resp.headers.get("Content-Encoding", "")
                raw = self._decode_body(raw, enc)
                if isinstance(raw, bytes):
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                else:
                    text = raw
                return {"code": resp.getcode(), "text": text, "url": resp.geturl()}
        except urllib.error.HTTPError as e:
            err = ""
            try:
                err = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            return {"code": e.code, "text": err, "url": url, "err": str(e)}
        except Exception as e:
            return {"code": -1, "text": "", "url": url, "err": str(e)}

    def _is_alive(self, base):
        try:
            r = self._fetch(base + "/v?order=createdAt", referer=base + "/")
            t = r.get("text") or ""
            return r.get("code") == 200 and len(t) > 500 and ("__NEXT_DATA__" in t or '"videos"' in t)
        except Exception:
            return False

    def _refresh_host(self):
        for base in FALLBACK_HOSTS:
            if self._is_alive(base):
                self.siteUrl = base
                try:
                    self.setCache("rouav_site", base)
                except Exception:
                    pass
                return base
        for nav in NAV_URLS:
            r = self._fetch(nav)
            text = r.get("text") or ""
            for h in re.findall(r"https?://(?:www\.)?rou[a-z0-9.-]+", text, re.I):
                try:
                    p = urllib.parse.urlparse(h)
                    base = "%s://%s" % (p.scheme, p.netloc)
                    if self._is_alive(base):
                        self.siteUrl = base
                        try:
                            self.setCache("rouav_site", base)
                        except Exception:
                            pass
                        return base
                except Exception:
                    continue
        self.siteUrl = HOST_DEFAULT
        return self.siteUrl

    def _fetch_heal(self, url, referer=None):
        r = self._fetch(url, referer=referer)
        t = r.get("text") or ""
        if r.get("code") == 200 and len(t) > 400:
            return r
        old = urllib.parse.urlparse(self.siteUrl).netloc
        self._refresh_host()
        new = urllib.parse.urlparse(self.siteUrl).netloc
        if old != new and url.startswith("http"):
            url = url.replace(old, new, 1)
        elif url.startswith("/"):
            url = self.siteUrl + url
        return self._fetch(url, referer=referer)

    # ---------- PNG / roUd 解包 ----------
    @staticmethod
    def _png_chunk_roud(body):
        if not body or body[:4] != b"\x89PNG":
            return None
        pos = 8
        while pos + 8 <= len(body):
            length = struct.unpack(">I", body[pos:pos + 4])[0]
            ctype = body[pos + 4:pos + 8]
            data = body[pos + 8:pos + 8 + length]
            if ctype == b"roUd":
                return data
            pos += 12 + length
            if ctype == b"IEND":
                break
        return None

    def _unwrap_payload(self, body):
        """
        返回 (kind, data)
        kind: 'm3u8' | 'ts' | 'raw'
        """
        if not body:
            return "raw", body
        if body.startswith(b"#EXT"):
            return "m3u8", body
        # 直接 TS
        if len(body) > 4 and body[0] == 0x47:
            return "ts", body
        roud = self._png_chunk_roud(body)
        if not roud or len(roud) < 2:
            return "raw", body
        flag = roud[0]
        payload = roud[1:]
        if flag == 1:
            try:
                return "m3u8", zlib.decompress(payload)
            except Exception:
                try:
                    return "m3u8", zlib.decompress(payload, -zlib.MAX_WBITS)
                except Exception:
                    return "raw", body
        if flag == 0:
            return "ts", payload
        # 未知 flag，尝试 zlib 或当 TS
        try:
            return "m3u8", zlib.decompress(payload)
        except Exception:
            if payload and payload[0] == 0x47:
                return "ts", payload
            return "raw", body

    def _resolve_hls_final(self, vid, html=None):
        api = "%s/api/hls/%s" % (self.siteUrl, vid)
        if html:
            m = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html, re.I)
            if m:
                try:
                    data = json.loads(m.group(1).strip())
                    ev = data.get("props", {}).get("pageProps", {}).get("ev") or {}
                    d, k = ev.get("d"), ev.get("k")
                    if d is not None and k is not None:
                        raw = base64.b64decode(d)
                        plain = bytes((b - int(k)) & 0xFF for b in raw).decode("utf-8", errors="ignore")
                        info = json.loads(plain)
                        vu = (info.get("videoUrl") or "").strip()
                        if vu.startswith("/"):
                            api = self.siteUrl + vu.split("?")[0]
                        elif vu.startswith("http"):
                            api = vu
                except Exception:
                    pass
        try:
            code, final, body = self._fetch_bytes(api, referer=self.siteUrl + "/v/" + vid)
            return final or api, body
        except Exception:
            return api, b""

    def _proxy_base(self):
        try:
            base = self.getProxyUrl(True)
            if base:
                return base
        except Exception:
            pass
        try:
            base = self.getProxyUrl()
            if base:
                return base
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def _make_proxy_url(self, do, target):
        base = self._proxy_base()
        sep = "&" if "?" in base else "?"
        return "%s%sdo=%s&url=%s" % (base, sep, do, urllib.parse.quote(target, safe=""))

    # ---------- 列表 ----------
    def _fmt_dur(self, sec):
        try:
            n = int(sec or 0)
        except Exception:
            return "HD"
        if not n:
            return "HD"
        m, s = divmod(n, 60)
        h, m = divmod(m, 60)
        if h:
            return "%d:%02d:%02d" % (h, m, s)
        return "%02d:%02d" % (m, s)

    def _pack_id(self, vid, title):
        payload = json.dumps({"vid": str(vid).strip(), "title": title}, ensure_ascii=False)
        b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")
        return "pkg_" + b64

    def _unpack_id(self, raw):
        raw = str(raw or "").strip()
        if raw.startswith("pkg_"):
            try:
                s = raw[4:]
                pad = len(s) % 4
                if pad:
                    s += "=" * (4 - pad)
                pkg = json.loads(base64.urlsafe_b64decode(s.encode("utf-8")).decode("utf-8"))
                return pkg.get("vid", ""), pkg.get("title", "")
            except Exception:
                return raw, ""
        if raw.startswith("/v/"):
            return raw[3:], ""
        return raw, ""

    def _parse_list(self, html):
        cards = []
        if not html:
            return cards
        m = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html, re.I)
        if m:
            try:
                data = json.loads(m.group(1).strip())
                videos = data.get("props", {}).get("pageProps", {}).get("videos") or []
                for v in videos:
                    vid = v.get("id") or v.get("vid") or ""
                    if not vid:
                        continue
                    name = html_lib.unescape(v.get("nameZh") or v.get("name") or "肉视频")
                    pic = v.get("coverImageUrl") or ""
                    cards.append({
                        "vod_id": self._pack_id(vid, name),
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": self._fmt_dur(v.get("duration")),
                        "style": {"type": "rect", "ratio": 1.78},
                    })
                if cards:
                    return cards
            except Exception:
                pass
        return cards

    def _build_list_url(self, tid, page):
        path = str(tid or "/v?order=createdAt").strip()
        if not path.startswith("/"):
            path = "/" + path
        sep = "&" if "?" in path else "?"
        raw = "%s%spage=%d" % (path, sep, page)
        return self.siteUrl + urllib.parse.quote(raw, safe="/?=&:%")

    # ---------- 接口 ----------
    def homeContent(self, filter=False):
        result = {"class": list(CLASS_LIST)}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        try:
            res = self.categoryContent("/v?order=createdAt", "1", False, {})
            return {"list": (res.get("list") or [])[:24]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            page = int(str(pg)) if str(pg).isdigit() else 1
            url = self._build_list_url(tid, page)
            r = self._fetch_heal(url)
            cards = self._parse_list(r.get("text") or "")
            return {
                "list": cards,
                "page": page,
                "pagecount": page + 1 if len(cards) >= 12 else page,
                "limit": len(cards),
                "total": 9999,
            }
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            raw = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
            vid, cached_title = self._unpack_id(raw)
            if not vid:
                return {"list": []}
            r = self._fetch_heal("/v/%s" % vid)
            html = r.get("text") or ""
            vod_name = cached_title
            vod_pic = ""
            tag_str = ""
            desc = ""
            m = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html, re.I)
            if m:
                try:
                    data = json.loads(m.group(1).strip())
                    video = data.get("props", {}).get("pageProps", {}).get("video") or {}
                    if video:
                        if not vod_name:
                            vod_name = html_lib.unescape(video.get("nameZh") or video.get("name") or "肉视频")
                        vod_pic = video.get("coverImageUrl") or ""
                        tags = video.get("tagsZh") or video.get("tags") or []
                        tag_str = ", ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")
                        desc = video.get("description") or ""
                except Exception:
                    pass
            if not vod_name:
                vod_name = "肉视频"

            # 解析最终 CDN（可能是 m3u8 或 PNG 壳）
            final, body = self._resolve_hls_final(vid, html=html)
            kind, _ = self._unwrap_payload(body) if body else ("raw", None)

            # 一律走本地代理解包，保证所有条目可播
            proxy_play = self._make_proxy_url("rouhls", final)
            api = "%s/api/hls/%s" % (self.siteUrl, vid)
            proxy_api = self._make_proxy_url("rouhls", api)

            content_parts = []
            if tag_str:
                content_parts.append("标签: %s" % tag_str)
            if desc:
                content_parts.append(desc)
            content_parts.append("节点: %s" % self.siteUrl)
            content_parts.append("流类型: %s" % kind)

            return {
                "list": [{
                    "vod_id": raw,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "HD正片",
                    "vod_content": "\n".join(content_parts),
                    "vod_play_from": "肉视频专线$$$API线路",
                    "vod_play_url": "正片$%s$$$正片$%s" % (proxy_play, proxy_api),
                }]
            }
        except Exception as e:
            print("detail error", e)
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            if not key:
                return {"list": [], "page": 1, "pagecount": 1}
            page = int(str(pg)) if str(pg).isdigit() else 1
            url = "%s/search?q=%s&page=%d" % (self.siteUrl, urllib.parse.quote(str(key).strip()), page)
            r = self._fetch_heal(url)
            cards = self._parse_list(r.get("text") or "")
            return {
                "list": cards,
                "page": page,
                "pagecount": page + 1 if len(cards) >= 12 else page,
                "limit": len(cards),
                "total": 9999,
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 0}

    def playerContent(self, flag, id, vipFlags=None):
        play_url = str(id or "").strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl,
            "Accept": "*/*",
        }
        # 已是代理地址直接播
        if "do=rouhls" in play_url or "do=routs" in play_url:
            return {"parse": 0, "jx": 0, "url": play_url, "header": headers}
        # 原始 API / CDN → 包一层代理
        if "/api/hls/" in play_url or "/hls/" in play_url or play_url.startswith("http"):
            play_url = self._make_proxy_url("rouhls", play_url)
        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": headers,
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        """
        do=rouhls : 解包 index.png/jpg → m3u8，并把分片改写到 do=routs
        do=routs  : 解包分片 PNG → video/mp2t
        """
        try:
            do = (param or {}).get("do") or (param or {}).get("type") or ""
            url = (param or {}).get("url") or ""
            if not url:
                return [404, "text/plain; charset=utf-8", b"missing url"]
            url = urllib.parse.unquote(url)

            code, final, body = self._fetch_bytes(url, referer=self.siteUrl + "/")
            kind, data = self._unwrap_payload(body)

            if do == "routs" or kind == "ts":
                if kind != "ts":
                    # 再尝试
                    kind, data = self._unwrap_payload(body)
                if kind == "ts" and data:
                    return [200, "video/mp2t", data]
                # 纯 TS 或回退原文
                if body and body[0:1] == b"G":
                    return [200, "video/mp2t", body]
                return [200, "application/octet-stream", body]

            # rouhls / 默认：输出 m3u8
            if kind != "m3u8" or not data:
                # 也许 final 需要再跟一次（极少）
                return [502, "text/plain; charset=utf-8", b"unwrap m3u8 failed"]

            text = data.decode("utf-8", errors="ignore") if isinstance(data, (bytes, bytearray)) else str(data)
            # 分片 URL 改写走 routs 代理
            lines = []
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#") and s.startswith("http"):
                    lines.append(self._make_proxy_url("routs", s))
                else:
                    lines.append(line)
            out = "\n".join(lines) + "\n"
            return [200, "application/vnd.apple.mpegurl", out.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain; charset=utf-8", str(e).encode("utf-8")]

    def destroy(self):
        self.options = {}
