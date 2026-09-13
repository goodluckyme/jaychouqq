# coding: utf-8
import json
import sys
import re
import urllib.request
import urllib.parse
import ssl

sys.path.append('..')
from base.spider import Spider

VERSION = '1.2.0'
SITE_URL = 'https://jav.sb'

# 固定分类（UTF-8 中文，避免乱码）
CATEGORIES = [
    {"type_id": "new", "type_name": "最近更新"},
    {"type_id": "uncensored", "type_name": "无码"},
    {"type_id": "reduce", "type_name": "无码破解"},
    {"type_id": "chinese", "type_name": "中文字幕"},
    {"type_id": "censored", "type_name": "有码"},
    {"type_id": "amateur", "type_name": "素人"},
    {"type_id": "vr", "type_name": "VR"},
    {"type_id": "idol", "type_name": "女优"},
    {"type_id": "big-tits", "type_name": "巨乳"},
    {"type_id": "anal", "type_name": "肛交"},
    {"type_id": "creampie", "type_name": "中出"},
    {"type_id": "lesbian", "type_name": "女同"},
    {"type_id": "mature", "type_name": "熟女"},
    {"type_id": "teen", "type_name": "少女"},
]


class Spider(Spider):
    def getName(self):
        return "JAV.SB"

    def init(self, extend=""):
        self.host = SITE_URL
        if extend:
            try:
                if isinstance(extend, str) and extend.strip().startswith('{'):
                    conf = json.loads(extend)
                    self.host = conf.get('host', SITE_URL).rstrip('/')
                elif isinstance(extend, dict):
                    self.host = extend.get('host', SITE_URL).rstrip('/')
            except Exception:
                pass

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _get(self, url, params=None):
        try:
            if params:
                qs = urllib.parse.urlencode(params)
                url = url + ('&' if '?' in url else '?') + qs
            req = urllib.request.Request(url, headers=self.headers, method='GET')
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=12)
            # 强制按 utf-8 解码，防止乱码
            raw = resp.read()
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('utf-8', errors='ignore')
        except Exception as e:
            print('_get error: %s -> %s' % (url, e), file=sys.stderr)
            return ''

    def _parse_list(self, html):
        if not html or len(html) < 500:
            return []
        videos = []
        seen = set()

        # 模式1：带封面的卡片
        pattern1 = re.compile(
            r'href=["\']([^"\']*(?:/v/|/video/|/watch/|/jav/|[A-Za-z0-9]{2,15}-[0-9]{2,6})[^"\']*)["\']'
            r'[^>]{0,300}'
            r'(?:title=["\']([^"\']{2,120})["\'])?'
            r'[\s\S]{0,500}?'
            r'(?:src|data-src|data-original|data-poster)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            re.I
        )
        for m in pattern1.finditer(html):
            href = m.group(1).strip()
            title = (m.group(2) or '').strip()
            pic = (m.group(3) or '').strip()
            if not href or href in seen:
                continue
            seen.add(href)
            if not title or len(title) < 2:
                continue
            vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
            videos.append({
                'vod_id': vid,
                'vod_name': re.sub(r'\s+', ' ', title)[:80],
                'vod_pic': pic if pic.startswith('http') else urllib.parse.urljoin(self.host, pic),
                'vod_remarks': ''
            })

        # 模式2：宽松链接
        if len(videos) < 6:
            pattern2 = re.compile(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*(?:<[^>]+>)*\s*([^<]{5,100}?)\s*<',
                re.I
            )
            for m in pattern2.finditer(html):
                href, title = m.group(1).strip(), m.group(2).strip()
                if not re.search(r'/v/|/video/|/watch/|[A-Za-z]{2,12}-[0-9]{2,6}', href, re.I):
                    continue
                if href in seen or len(title) < 4:
                    continue
                seen.add(href)
                vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
                videos.append({
                    'vod_id': vid,
                    'vod_name': re.sub(r'\s+', ' ', title)[:80],
                    'vod_pic': '',
                    'vod_remarks': ''
                })

        return videos

    def _extract_play_urls(self, html, page_url=''):
        """提取真实播放地址，优先 m3u8 / 高清 mp4"""
        play_list = []
        seen = set()

        def add(u, label=None):
            u = u.replace('\\/', '/').replace('&amp;', '&').strip()
            if not u.startswith('http') or u in seen:
                return
            seen.add(u)
            if not label:
                if '.m3u8' in u.lower():
                    label = 'HLS'
                elif '1080' in u:
                    label = '1080P'
                elif '720' in u:
                    label = '720P'
                elif '480' in u:
                    label = '480P'
                else:
                    label = '播放'
            play_list.append((label, u))

        # 1. 直接匹配 m3u8 / mp4
        for m in re.finditer(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', html, re.I):
            add(m.group(0), 'HLS')
        for m in re.finditer(r'https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', html, re.I):
            add(m.group(0))

        # 2. source / video 标签
        for m in re.finditer(r'<(?:source|video)[^>]+src=["\']([^"\']+)["\']', html, re.I):
            add(m.group(1))

        # 3. 常见 JS 变量
        for key in ('url', 'src', 'file', 'video', 'playurl', 'videoUrl', 'hls', 'm3u8', 'source'):
            m = re.search(rf'["\']?{key}["\']?\s*[:=]\s*["\'](https?://