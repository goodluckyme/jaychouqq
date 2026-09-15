# -*- coding: utf-8 -*-
"""
肉视频 (rou.video) 爬虫
- 风格对齐爱看机器人：清晰接口 + Session 请求
- 列表：__NEXT_DATA__.videos
- 播放：/api/hls/{id} 302 → CDN .../index.png (站点专用 HLS 伪装)
"""
import sys
import re
import json
import base64
import html as html_lib
import gzip
import zlib
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

# 分类
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
        return any(k in low for k in (
            ".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png", "/hls/"
        ))

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
        }

    def _decode_body(self, raw, enc=""):
        if not raw:
            return ""
        if raw[:2] == b"\x1f\x8b" or enc == "gzip":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw)
            except Exception:
                try:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:
                    pass
        try:
            return raw.decode("utf-8")
        except Exception:
            return raw.decode("latin1", errors="ignore")

    def _fetch(self, url, referer=None, timeout=15, accept=None):
        if not url:
            return {"code": 0, "text": "", "url": ""}
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = self.siteUrl + url
        try:
            req = urllib.request.Request(url, headers=self._headers(referer, accept))
            with self.opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                enc = resp.headers.get("Content-Encoding", "")
                text = self._decode_body(raw, enc)
                return {"code": resp.getcode(), "text": text, "url": resp.geturl()}
        except urllib.error.HTTPError as e:
            err_text = ""
            try:
                err_text = self._decode_body(e.read(), "")
            except Exception:
                pass
            return {"code": e.code, "text": err_text, "url": url, "err": str(e)}
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
        # 备用直连
        for base in FALLBACK_HOSTS:
            if self._is_alive(base):
                self.siteUrl = base
                try:
                    self.setCache("rouav_site", base)
                except Exception:
                    pass
                return base

        # 导航站
        for nav in NAV_URLS:
            r = self._fetch(nav)
            text = r.get("text") or ""
            if not text:
                continue
            for h in re.findall(r'https?://(?:www\.)?rou[a-z0-9.-]+', text, re.I):
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
            for b in re.findall(r'["\']([A-Za-z0-9+/=]{80,})["\']', text):
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    try:
                        decoded = urllib.parse.unquote(decoded)
                    except Exception:
                        pass
                    if "[" not in decoded:
                        continue
                    low = decoded.lower()
                    if "rou" not in low and "肉" not in low:
                        continue
                    for item in json.loads(decoded):
                        name = str(item.get("name") or "").lower()
                        if name not in ("rouav", "rou", "肉视频", "rou.video") and "rou" not in name:
                            continue
                        cands = []
                        if item.get("url"):
                            cands.append(item["url"])
                        for uo in item.get("urls") or []:
                            u = uo.get("url") if isinstance(uo, dict) else uo
                            if u:
                                cands.append(u)
                        for c in cands:
                            p = urllib.parse.urlparse(c)
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

        # HTML 兜底
        seen = set()
        for href, block in re.findall(r'<a[^>]+href=["\'](/v/([a-zA-Z0-9]+))["\'][^>]*>([\s\S]*?)</a>', html, re.I):
            vid = href.replace("/v/", "").strip("/")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            img = ""
            for pat in (r'data-src=["\']([^"\']+)["\']', r'src=["\']([^"\']+)["\']'):
                im = re.search(pat, block, re.I)
                if im and "data:image" not in im.group(1) and not im.group(1).endswith(".svg"):
                    img = im.group(1).strip()
                    break
            if img.startswith("//"):
                img = "https:" + img
            elif img.startswith("/"):
                img = self.siteUrl + img
            tm = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', block, re.I)
            title = html_lib.unescape(tm.group(1).strip() if tm else "肉视频")
            dm = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', block)
            cards.append({
                "vod_id": self._pack_id(vid, title),
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": dm.group(1) if dm else "HD",
                "style": {"type": "rect", "ratio": 1.78},
            })
        return cards

    def _build_list_url(self, tid, page):
        path = str(tid or "/v?order=createdAt").strip()
        if not path.startswith("/"):
            path = "/" + path
        sep = "&" if "?" in path else "?"
        raw = "%s%spage=%d" % (path, sep, page)
        # 中文 tag 编码，保留 /?=
        return self.siteUrl + urllib.parse.quote(raw, safe="/?=&:%")

    # ---------- 播放解析 ----------
    def _resolve_hls(self, vid):
        """请求 /api/hls/{vid}，跟随 302 得到最终 CDN index.png 地址"""
        api = "%s/api/hls/%s" % (self.siteUrl, vid)
        try:
            headers = self._headers(referer=self.siteUrl + "/v/" + vid, accept="*/*")
            req = urllib.request.Request(api, headers=headers)
            with self.opener.open(req, timeout=12) as resp:
                final = resp.geturl() or api
                # 读一点点确保连通（index.png 约 1KB）
                _ = resp.read(32)
                if final and final != api:
                    return final
                return final or api
        except urllib.error.HTTPError as e:
            # 部分环境 302 被转成 HTTPError
            loc = e.headers.get("Location") if e.headers else None
            if loc:
                if loc.startswith("/"):
                    loc = self.siteUrl + loc
                return loc
        except Exception:
            pass
        return api

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
            if not vod_pic:
                cm = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
                if not cm:
                    cm = re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
                if cm:
                    vod_pic = cm.group(1).strip()

            # 预解析最终流地址（修复客户端不跟随 302 导致无法播放）
            stream = self._resolve_hls(vid)
            api = "%s/api/hls/%s" % (self.siteUrl, vid)

            # 播放列表：优先最终 CDN，其次 API（再由 player 解析）
            play_from = []
            play_url = []
            if stream and stream != api and ("index.png" in stream or "/hls/" in stream):
                play_from.append("肉视频专线")
                play_url.append("正片$%s" % stream)
            play_from.append("API线路")
            play_url.append("正片$%s" % api)

            content_parts = []
            if tag_str:
                content_parts.append("标签: %s" % tag_str)
            if desc:
                content_parts.append(desc)
            content_parts.append("节点: %s" % self.siteUrl)

            return {
                "list": [{
                    "vod_id": raw,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "HD正片",
                    "vod_content": "\n".join(content_parts),
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url": "$$$".join(play_url),
                }]
            }
        except Exception:
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
            "Connection": "keep-alive",
        }

        # 若仍是 API 地址，再解析一次最终流
        if "/api/hls/" in play_url:
            try:
                m = re.search(r'/api/hls/([a-zA-Z0-9]+)', play_url)
                if m:
                    resolved = self._resolve_hls(m.group(1))
                    if resolved:
                        play_url = resolved
            except Exception:
                pass

        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": headers,
        }

    def localProxy(self, param):
        pass

    def destroy(self):
        self.options = {}
