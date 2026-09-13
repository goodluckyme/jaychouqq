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
            m = re.search(rf'["\']?{key}["\']?\s*[:=]\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
            if m:
                add(m.group(1))

        # 4. 去重后按清晰度排序（HLS > 1080 > 720 > 其他）
        def sort_key(item):
            label, u = item
            if 'HLS' in label or '.m3u8' in u.lower():
                return 0
            if '1080' in label or '1080' in u:
                return 1
            if '720' in label or '720' in u:
                return 2
            return 3

        play_list.sort(key=sort_key)
        return play_list

    def homeContent(self, filter):
        # 分类固定返回，保证不乱码、不丢失
        classes = []
        for c in CATEGORIES:
            classes.append({
                'type_id': c['type_id'],
                'type_name': c['type_name']
            })

        videos = []
        try:
            html = self._get(self.host + '/')
            videos = self._parse_list(html)
        except Exception as e:
            print('homeContent list error:', e, file=sys.stderr)

        return {
            'class': classes,
            'list': videos[:24]
        }

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'new')

        candidates = []
        if pg <= 1:
            candidates.extend([
                f'{self.host}/{tid}/',
                f'{self.host}/c/{tid}/',
                f'{self.host}/category/{tid}/',
                f'{self.host}/genre/{tid}/',
                f'{self.host}/tag/{tid}/',
            ])
        candidates.extend([
            f'{self.host}/{tid}/page/{pg}/',
            f'{self.host}/c/{tid}/page/{pg}/',
            f'{self.host}/category/{tid}/page/{pg}/',
            f'{self.host}/{tid}/?page={pg}',
            f'{self.host}/?c={tid}&page={pg}',
        ])
        if pg == 1:
            candidates.append(self.host + '/')

        videos = []
        for url in candidates:
            html = self._get(url)
            videos = self._parse_list(html)
            if len(videos) >= 6:
                break

        type_name = tid
        for c in CATEGORIES:
            if c['type_id'] == tid:
                type_name = c['type_name']
                break

        return {
            'page': pg,
            'pagecount': 9999 if len(videos) >= 10 else pg,
            'limit': 24,
            'total': 9999 if videos else 0,
            'type_name': type_name,
            'list': videos
        }

    def detailContent(self, array):
        result = {'list': []}
        if not array or not array[0]:
            return result

        page_url = str(array[0])
        if not page_url.startswith('http'):
            page_url = urllib.parse.urljoin(self.host, page_url)

        html = self._get(page_url)
        vod = {
            'vod_id': page_url,
            'vod_name': '视频详情',
            'vod_pic': '',
            'vod_remarks': '',
            'vod_content': '',
            'vod_play_from': 'JAV.SB',
            'vod_play_url': ''
        }

        # 标题
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', html, re.I)
        if m:
            name = re.sub(r'\s*[-|].*$', '', m.group(1)).strip()
            vod['vod_name'] = name[:80] if name else '视频详情'

        # 封面
        m = re.search(r'(?:og:image|poster)=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            pic = m.group(1)
            vod['vod_pic'] = pic if pic.startswith('http') else urllib.parse.urljoin(self.host, pic)

        # 播放地址
        play_list = self._extract_play_urls(html, page_url)
        if play_list:
            parts = [f'{label}${url}' for label, url in play_list[:6]]
            vod['vod_play_url'] = '#'.join(parts)
        else:
            # 没有直链时返回页面，让播放器再解析一次
            vod['vod_play_url'] = f'播放${page_url}'

        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        q = urllib.parse.quote(key)
        urls = [
            f'{self.host}/search/{q}/',
            f'{self.host}/search/{q}/page/{pg}/',
            f'{self.host}/search?keyword={q}&page={pg}',
            f'{self.host}/?s={q}&page={pg}',
        ]
        videos = []
        for url in urls:
            html = self._get(url)
            videos = self._parse_list(html)
            if videos:
                break
        return {
            'page': pg,
            'pagecount': 9999 if len(videos) >= 10 else pg,
            'limit': 24,
            'total': 9999,
            'list': videos
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        play = str(id or '').strip()

        # 已经是媒体地址
        if play.startswith('http') and re.search(r'\.(m3u8|mp4|flv|mpd)(\?|$)', play, re.I):
            return {
                'parse': 0,
                'jx': '0',
                'url': play,
                'header': header
            }

        # 页面地址 → 再提取一次
        if play.startswith('http'):
            html = self._get(play)
            play_list = self._extract_play_urls(html, play)
            if play_list:
                # 返回清晰度最高的一条
                return {
                    'parse': 0,
                    'jx': '0',
                    'url': play_list[0][1],
                    'header': header
                }

        return {
            'parse': 1,
            'jx': '1',
            'url': play,
            'header': header
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(m3u8|mp4|flv|mpd)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}