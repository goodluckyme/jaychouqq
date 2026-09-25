#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 黄豆短剧 / momodrift.top - 蜂蜜影视原生 Python 蜘蛛
# 说明：momodrift.top 为 Flutter SPA + AES-GCM 加密 API；
#       同源可解析站 hddj.tv 提供 HTML 列表/详情与 /play/{id}/{ep}.m3u8 直链。

import sys
import re
import json
import gzip
import zlib
import ssl
import http.cookiejar
import urllib.request
import urllib.parse
from urllib.parse import quote

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
        # 用户指定域名（SPA）；实际内容解析走同源 HTML 站
        self.siteUrl = "https://momodrift.top"
        self.htmlHost = "https://hddj.tv"
        self._ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
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
            self.siteUrl = host.rstrip("/")
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
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.htmlHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer or (self.htmlHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=15) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {
                        "code": code,
                        "text": text,
                        "bytes": raw,
                        "err": "",
                        "final_url": final_url,
                    }
            except Exception as e:
                if attempt == 0:
                    continue
                return {
                    "code": -1,
                    "text": "",
                    "bytes": b"",
                    "err": str(e),
                    "final_url": target_url,
                }
        return {"code": -1, "text": "", "bytes": b"", "err": "timeout", "final_url": target_url}

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
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def homeContent(self, filter):
        classes = [
            {"type_name": "首页推荐", "type_id": "home"},
            {"type_name": "魔改短剧", "type_id": "mgdj"},
            {"type_name": "AI短剧", "type_id": "ai"},
            {"type_name": "原创短剧", "type_id": "yuandou"},
            {"type_name": "UP主播", "type_id": "up-zhubo"},
            {"type_name": "真人短剧", "type_id": "real"},
            {"type_name": "二次元", "type_id": "erciyuan"},
            {"type_name": "黑料", "type_id": "heiliao"},
            {"type_name": "VIP专区", "type_id": "vip-zone"},
            {"type_name": "品牌", "type_id": "brand"},
        ]
        result = {"class": classes}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        res = self.categoryContent("home", 1, False, {})
        return {"list": res.get("list", [])[:24]}

    def _parse_cards(self, html_text):
        vod_list = []
        seen = set()
        # 主卡片：.dm-card 内链到 /series/details/{id}.html
        for m in re.finditer(
            r'<a[^>]+href=["\']((?:https?://[^/]+)?/series/details/([a-zA-Z0-9]+)\.html)["\'][^>]*>([\s\S]{0,2500}?)</a>',
            html_text,
            re.I,
        ):
            href, sid, body = m.group(1), m.group(2), m.group(3)
            if sid in seen:
                continue
            seen.add(sid)
            title = ""
            tm = re.search(r'(?:dm-card-title|title)[^>]*>([\s\S]*?)<', body, re.I)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                am = re.search(r'alt=["\']([^"\']+)["\']', body)
                if am:
                    title = am.group(1).strip()
            if not title:
                title = "短剧 " + sid
            pic = ""
            pm = re.search(
                r'(?:data-src|data-original|src)=["\']([^"\']+)["\']', body, re.I
            )
            if pm and "favicon" not in pm.group(1):
                pic = self._abs(pm.group(1))
            remarks = ""
            rm = re.search(r'(?:dm-card-heat|heat|flag)[^>]*>([\s\S]*?)<', body, re.I)
            if rm:
                remarks = self._clean(rm.group(1))[:30]
            vod_list.append(
                {
                    "vod_id": sid,
                    "vod_name": title[:80],
                    "vod_pic": pic,
                    "vod_remarks": remarks or "黄豆短剧",
                }
            )
            if len(vod_list) >= 80:
                break
        # 兜底：纯 details 链接
        if not vod_list:
            for m in re.finditer(
                r'href=["\'](?:https?://[^/]+)?/series/details/([a-zA-Z0-9]+)\.html["\']',
                html_text,
            ):
                sid = m.group(1)
                if sid in seen:
                    continue
                seen.add(sid)
                vod_list.append(
                    {
                        "vod_id": sid,
                        "vod_name": "短剧 " + sid,
                        "vod_pic": "",
                        "vod_remarks": "黄豆短剧",
                    }
                )
                if len(vod_list) >= 40:
                    break
        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        page = int(pg) if pg else 1
        slug = str(tid or "home").strip()

        if slug in ("home", "", "index"):
            path = "/" if page <= 1 else ("/?page=%d" % page)
        else:
            path = "/category/%s/" % slug
            if page > 1:
                path += "?page=%d" % page

        res = self._fetch(self.htmlHost + path)
        html_text = res.get("text", "")
        vod_list = self._parse_cards(html_text)
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

        title = "短剧 " + sid
        cover = ""
        desc = ""
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            title = self._clean(m.group(1))
        if not title or title == "短剧 " + sid:
            m = re.search(r'data-title=["\']([^"\']+)["\']', html)
            if m:
                title = m.group(1).strip()
        m = re.search(r'data-(?:video-cover|poster)=["\']([^"\']+)["\']', html)
        if m:
            cover = self._abs(m.group(1))
        m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
            html,
            re.I,
        )
        if m:
            desc = m.group(1).strip()

        # 集数：data-eps
        ep_count = 1
        m = re.search(r'data-eps=["\'](\d+)["\']', html)
        if m:
            ep_count = max(1, int(m.group(1)))
        # 页面上其它 ep 标记
        eps_found = set(int(x) for x in re.findall(r'/play/%s/(\d+)' % re.escape(sid), html))
        eps_found.update(int(x) for x in re.findall(r'[?&]ep=(\d+)', html))
        if eps_found:
            ep_count = max(ep_count, max(eps_found))

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
                    "vod_director": "momodrift",
                    "vod_remarks": "共%d集" % ep_count,
                    "vod_content": desc or title,
                    "vod_play_from": "黄豆线路",
                    "vod_play_url": "#".join(episodes),
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        raw_url = str(id).strip()
        if raw_url.startswith("/"):
            raw_url = self.htmlHost + raw_url
        headers = {
            "User-Agent": self._ua,
            "Referer": self.htmlHost + "/",
            "Origin": self.htmlHost,
        }
        return {
            "parse": 0,
            "playUrl": "",
            "url": raw_url,
            "header": headers,
        }

    def searchContent(self, key, quick, pg="1"):
        del quick
        page = int(pg) if pg else 1
        q = quote(key)
        url = "%s/search/?q=%s" % (self.htmlHost, q)
        if page > 1:
            url += "&page=%d" % page
        res = self._fetch(url)
        vod_list = self._parse_cards(res.get("text", ""))
        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 10 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list,
        }

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return None

    def destroy(self):
        self.options = {}
