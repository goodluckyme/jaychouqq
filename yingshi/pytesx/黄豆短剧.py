#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 黄豆短剧 - 蜂蜜影视原生 Python 蜘蛛
# 内容站：https://hddj.tv  播放：/play/{id}/{ep}.m3u8

import re
import json
import gzip
import zlib
import ssl
import http.cookiejar
import urllib.request
import urllib.parse

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://hddj.tv"
        self.htmlHost = "https://hddj.tv"
        self._ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
        )
        self.options = {}
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx),
        )
        self.classes = [
            {"type_id": "home", "type_name": "首页推荐"},
            {"type_id": "mgdj", "type_name": "魔改短剧"},
            {"type_id": "ai", "type_name": "AI短剧"},
            {"type_id": "yuandou", "type_name": "原创短剧"},
            {"type_id": "up-zhubo", "type_name": "UP主播"},
            {"type_id": "real", "type_name": "真人短剧"},
            {"type_id": "erciyuan", "type_name": "二次元"},
            {"type_id": "heiliao", "type_name": "黑料"},
            {"type_id": "vip-zone", "type_name": "VIP专区"},
            {"type_id": "brand", "type_name": "品牌"},
            {"type_id": "cbdj", "type_name": "重磅短剧"},
        ]

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        host = self.options.get("host") or self.options.get("url") or ""
        if isinstance(host, str) and host.startswith("http"):
            self.htmlHost = host.rstrip("/")
            self.siteUrl = self.htmlHost
        return True

    def getName(self):
        return "黄豆短剧"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.htmlHost + target_url
        headers = {
            "User-Agent": self._ua,
            "Referer": referer or (self.htmlHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read()
                enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                return {
                    "code": resp.getcode(),
                    "text": raw.decode("utf-8", "ignore"),
                    "err": "",
                    "final_url": resp.geturl(),
                }
        except Exception as e:
            return {"code": 0, "text": "", "err": str(e), "final_url": target_url}

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.htmlHost + url
        return url

    def _clean(self, s):
        s = re.sub(r"<[^>]+>", " ", s or "")
        return re.sub(r"\s+", " ", s).strip()

    def _parse_cards(self, html_text):
        vod_list = []
        seen = set()
        html_text = html_text or ""

        # 主结构：<article class="dm-card" ...>
        for m in re.finditer(
            r'<article[^>]*class=["\'][^"\']*dm-card[^"\']*["\'][^>]*>([\s\S]*?)</article>',
            html_text,
            re.I,
        ):
            body = m.group(1)
            hm = re.search(
                r'href=["\'](?:https?://[^/]+)?(/series/details/([a-zA-Z0-9]+)\.html)["\']',
                body,
                re.I,
            )
            if not hm:
                continue
            sid = hm.group(2)
            if sid in seen:
                continue
            seen.add(sid)

            title = ""
            for pat in [
                r'aria-label=["\']([^"\']+)["\']',
                r'alt=["\']([^"\']+)["\']',
                r'class=["\'][^"\']*dm-card-title[^"\']*["\'][^>]*>([\s\S]*?)</',
                r'title=["\']([^"\']+)["\']',
            ]:
                tm = re.search(pat, body, re.I)
                if tm:
                    title = self._clean(tm.group(1))
                    if title and title not in ("黄豆短剧",):
                        break
                    title = ""
            if not title:
                title = "短剧 " + sid[:8]

            pic = ""
            pm = re.search(
                r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+)["\']',
                body,
                re.I,
            )
            if pm and "placeholder" not in pm.group(1) and "favicon" not in pm.group(1):
                pic = self._abs(pm.group(1))

            tips = ""
            rm = re.search(
                r'class=["\'][^"\']*dm-card-heat[^"\']*["\'][^>]*>([\s\S]*?)</span>',
                body,
                re.I,
            )
            if rm:
                tips = self._clean(rm.group(1))[:20]

            vod_list.append(
                {
                    "vod_id": sid,
                    "vod_name": title[:80],
                    "vod_pic": pic,
                    "vod_remarks": tips or "黄豆短剧",
                }
            )
            if len(vod_list) >= 80:
                break

        # 兜底：纯 details 链接
        if not vod_list:
            for m in re.finditer(
                r'href=["\'](?:https?://[^/]+)?/series/details/([a-zA-Z0-9]+)\.html["\']',
                html_text,
                re.I,
            ):
                sid = m.group(1)
                if sid in seen:
                    continue
                seen.add(sid)
                vod_list.append(
                    {
                        "vod_id": sid,
                        "vod_name": "短剧 " + sid[:8],
                        "vod_pic": "",
                        "vod_remarks": "黄豆短剧",
                    }
                )
                if len(vod_list) >= 40:
                    break
        return vod_list

    def homeContent(self, filter):
        return {"class": self.classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        res = self.categoryContent("home", "1", False, {})
        return {"list": res.get("list", [])[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        page = int(pg) if str(pg).isdigit() else 1
        slug = str(tid or "home").strip()

        if slug in ("home", "", "index"):
            path = "/" if page <= 1 else ("/?page=%d" % page)
        else:
            path = "/category/%s/" % slug
            if page > 1:
                path += "?page=%d" % page

        res = self._fetch(self.htmlHost + path)
        vod_list = self._parse_cards(res.get("text", ""))
        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": len(vod_list) or 24,
            "total": 9999,
            "list": vod_list,
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        sid = re.sub(r"\.html$", "", str(raw_id).strip("/").split("/")[-1])
        detail_url = "%s/series/details/%s.html" % (self.htmlHost, sid)
        res = self._fetch(detail_url)
        html = res.get("text", "")

        title = "短剧 " + sid[:8]
        cover = ""
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
        if m:
            title = self._clean(m.group(1)) or title
        if not title or title.startswith("短剧 "):
            m = re.search(r'aria-label=["\']([^"\']+)["\']', html)
            if m:
                title = m.group(1).strip()
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if m:
            cover = self._abs(m.group(1))
        if not cover:
            m = re.search(r'<img[^>]+class=["\'][^"\']*dm-card-img[^"\']*["\'][^>]+src=["\']([^"\']+)', html, re.I)
            if m:
                cover = self._abs(m.group(1))

        ep_count = 1
        m = re.search(r'data-eps=["\'](\d+)["\']', html)
        if m:
            ep_count = max(1, int(m.group(1)))
        eps = set(int(x) for x in re.findall(r"/play/%s/(\d+)" % re.escape(sid), html))
        if eps:
            ep_count = max(ep_count, max(eps))

        episodes = []
        for i in range(1, ep_count + 1):
            play = "%s/play/%s/%d.m3u8" % (self.htmlHost, sid, i)
            episodes.append("第%d集$%s" % (i, play))

        return {
            "list": [
                {
                    "vod_id": sid,
                    "vod_name": title,
                    "vod_pic": cover,
                    "vod_actor": "黄豆短剧",
                    "vod_director": "hddj",
                    "vod_content": title,
                    "vod_play_from": "黄豆",
                    "vod_play_url": "#".join(episodes),
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.htmlHost + "/",
            "Accept": "*/*",
        }
        return {
            "parse": 0 if self.isVideoFormat(play_url) else 1,
            "jx": 0,
            "url": play_url,
            "header": headers,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        q = urllib.parse.quote(key or "")
        url = "%s/search/?q=%s" % (self.htmlHost, q)
        if page > 1:
            url += "&page=%d" % page
        res = self._fetch(url)
        vod_list = self._parse_cards(res.get("text", ""))
        # 搜索页可能结构不同，再兜底
        if not vod_list:
            for m in re.finditer(
                r'/series/details/([a-zA-Z0-9]+)\.html',
                res.get("text", ""),
            ):
                sid = m.group(1)
                vod_list.append(
                    {
                        "vod_id": sid,
                        "vod_name": key or sid,
                        "vod_pic": "",
                        "vod_remarks": "搜索",
                    }
                )
                if len(vod_list) >= 30:
                    break
        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list,
        }

    def action(self, action):
        return {"msg": "黄豆短剧 ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
