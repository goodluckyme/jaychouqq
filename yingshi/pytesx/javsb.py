# coding: utf-8
import json
import sys
import re
import urllib.request
import urllib.parse
import ssl
from html.parser import HTMLParser

sys.path.append('..')
from base.spider import Spider

VERSION = '1.0.0'

SITE_URL = 'https://jav.sb'

# 常见 JAV 分类（可根据实际页面调整 type_id）
CATEGORIES = [
    {"type_id": "censored", "type_name": "有码"},
    {"type_id": "uncensored", "type_name": "无码"},
    {"type_id": "reduce", "type_name": "无码破解"},
    {"type_id": "chinese", "type_name": "中文字幕"},
    {"type_id": "amateur", "type_name": "素人"},
    {"type_id": "vr", "type_name": "VR"},
    {"type_id": "trending", "type_name": "热门"},
    {"type_id": "new", "type_name": "最新"},
    {"type_id": "jav-idol", "type_name": "女优"},
    {"type_id": "big-tits", "type_name": "巨乳"},
    {"type_id": "anal", "type_name": "肛交"},
    {"type_id": "creampie", "type_name": "中出"},
    {"type_id": "lesbian", "type_name": "女同"},
    {"type_id": "mature", "type_name": "熟女"},
    {"type_id": "teen", "type_name": "少女"},
]


class SimpleListParser(HTMLParser):
    """简单提取视频卡片"""
    def __init__(self):
        super().__init__()
        self.videos = []
        self._curr = None
        self._in_title = False
        self._in_a = False
        self._href = ''
        self._title = ''
        self._pic = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            href = attrs.get('href', '')
            if re.search(r'/(v|video|watch|jav)/|/[a-z0-9]+-[0-9]+', href, re.I):
                self._in_a = True
                self._href = href
                self._title = attrs.get('title', '')
        if tag == 'img' and self._in_a:
            self._pic = attrs.get('data-src') or attrs.get('data-original') or attrs.get('src', '')

    def handle_data(self, data):
        if self._in_a and data.strip() and not self._title:
            self._title = data.strip()

    def handle_endtag(self, tag):
        if tag == 'a' and self._in_a:
            if self._href and self._title:
                vid = self._href
                if not vid.startswith('http'):
                    vid = urllib.parse.urljoin(SITE_URL, vid)
                self.videos.append({
                    'vod_id': vid,
                    'vod_name': re.sub(r'\s+', ' ', self._title)[:80],
                    'vod_pic': self._pic if self._pic.startswith('http') else urllib.parse.urljoin(SITE_URL, self._pic),
                    'vod_remarks': ''
                })
            self._in_a = False
            self._href = ''
            self._title = ''
            self._pic = ''


class Spider(Spider):
    def getName(self):
        return "JAV.SB"

    def init(self, extend=""):
        if extend:
            try:
                if isinstance(extend, str) and extend.startswith('{'):
                    conf = json.loads(extend)
                    self.host = conf.get('host', SITE_URL).rstrip('/')
                elif isinstance(extend, dict):
                    self.host = extend.get('host', SITE_URL).rstrip('/')
                else:
                    self.host = SITE_URL
            except Exception:
                self.host = SITE_URL
        else:
            self.host = SITE_URL

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
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=15)
            return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print('_get error: %s -> %s' % (url, e), file=sys.stderr)
            return ''

    def _parse_list(self, html):
        if not html:
            return []
        parser = SimpleListParser()
        try:
            parser.feed(html)
        except Exception:
            pass
        # 正则兜底
        if not parser.videos:
            for m in re.finditer(
                r'href=["\']([^"\']+(?:/v/|/video/|/watch/|[a-z0-9]+-[0-9]+)[^"\']*)["\'][^>]*>[\s\S]{0,300}?(?:src|data-src|data-original)=["\']([^"\']+)["\'][\s\S]{0,200}?>([^<]{4,80})<',
                html, re.I
            ):
                href, pic, title = m.group(1), m.group(2), m.group(3).strip()
                if not title:
                    continue
                vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
                parser.videos.append({
                    'vod_id': vid,
                    'vod_name': re.sub(r'\s+', ' ', title)[:80],
                    'vod_pic': pic if pic.startswith('http') else urllib.parse.urljoin(self.host, pic),
                    'vod_remarks': ''
                })
        # 去重
        seen = set()
        result = []
        for v in parser.videos:
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                result.append(v)
        return result

    def homeContent(self, filter):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in CATEGORIES]
        # 首页最新
        html = self._get(self.host + '/')
        videos = self._parse_list(html)
        return {'class': classes, 'list': videos[:24]}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        # 常见分类路径尝试
        paths = [
            f'{self.host}/c/{tid}/page/{pg}/',
            f'{self.host}/category/{tid}/page/{pg}/',
            f'{self.host}/{tid}/page/{pg}/',
            f'{self.host}/c/{tid}/?page={pg}',
            f'{self.host}/?c={tid}&page={pg}',
        ]
        if pg == 1:
            paths = [
                f'{self.host}/c/{tid}/',
                f'{self.host}/category/{tid}/',
                f'{self.host}/{tid}/',
            ] + paths

        videos = []
        for url in paths:
            html = self._get(url)
            videos = self._parse_list(html)
            if videos:
                break

        type_name = tid
        for c in CATEGORIES:
            if c['type_id'] == tid:
                type_name = c['type_name']
                break

        return {
            'page': pg,
            'pagecount': 9999 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': 9999,
            'type_name': type_name,
            'list': videos
        }

    def detailContent(self, array):
        result = {'list': []}
        if not array or not array[0]:
            return result

        page_url = array[0]
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
            vod['vod_name'] = re.sub(r'\s*[-|].*$', '', m.group(1)).strip()[:80]

        # 封面
        m = re.search(r'(?:og:image|poster|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            pic = m.group(1)
            vod['vod_pic'] = pic if pic.startswith('http') else urllib.parse.urljoin(self.host, pic)

        # 播放地址提取
        play_list = []
        # m3u8 / mp4
        for m in re.finditer(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)[^"\'\s<>]*', html, re.I):
            u = m.group(0).replace('\\/', '/')
            if u not in play_list:
                play_list.append(u)
        # source / video 标签
        for m in re.finditer(r'<(?:source|video)[^>]+src=["\']([^"\']+)["\']', html, re.I):
            u = m.group(1)
            if u.startswith('http') and u not in play_list:
                play_list.append(u)

        if play_list:
            parts = []
            for i, u in enumerate(play_list[:5]):
                label = '播放' if i == 0 else f'线路{i+1}'
                if 'm3u8' in u:
                    label = 'HLS'
                elif '1080' in u:
                    label = '1080P'
                elif '720' in u:
                    label = '720P'
                parts.append(f'{label}${u}')
            vod['vod_play_url'] = '#'.join(parts)
        else:
            # 无直链时返回页面，交给解析
            vod['vod_play_url'] = f'播放${page_url}'

        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        q = urllib.parse.quote(key)
        urls = [
            f'{self.host}/search/{q}/page/{pg}/',
            f'{self.host}/search/{q}/?page={pg}',
            f'{self.host}/?s={q}&page={pg}',
            f'{self.host}/search?keyword={q}&page={pg}',
        ]
        videos = []
        for url in urls:
            html = self._get(url)
            videos = self._parse_list(html)
            if videos:
                break
        return {
            'page': pg,
            'pagecount': 9999 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': 9999,
            'list': videos
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
        }
        play = str(id or '')
        if play.startswith('http') and re.search(r'\.(m3u8|mp4|flv)', play, re.I):
            return {
                'parse': 0,
                'playUrl': '',
                'url': play,
                'header': header
            }
        # 再请求一次提取
        if play.startswith('http'):
            html = self._get(play)
            m = re.search(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)', html, re.I)
            if m:
                return {
                    'parse': 0,
                    'playUrl': '',
                    'url': m.group(0).replace('\\/', '/'),
                    'header': header
                }
        return {
            'parse': 1,
            'playUrl': '',
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