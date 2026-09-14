# coding: utf-8
"""
JAV.SB Spider  v1.4.0
修复：分类路径错误导致无数据
真实结构：
  首页     /en/
  分类     /en/javtype/{Name}.html  或  /en/vod/show/by/hits/id/{Name}.html
  分页     ?page=N  或  /en/javtype/{Name}-{N}.html
  搜索     /en/vod/search/by/time/wd/{kw}.html
  详情     /en/jav/{id}.html
"""
import json
import sys
import re
import urllib.request
import urllib.parse
import ssl
import http.cookiejar

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass

VERSION = '1.4.0'
SITE_URL = 'https://jav.sb'

# type_id -> 站点真实路径名（优先 javtype，其次 vod/show）
CATEGORIES = [
    {"type_id": "new", "type_name": "最近更新", "paths": ["/en/", "/en/vod/search.html"]},
    {"type_id": "uncensored", "type_name": "无码", "paths": [
        "/en/javtype/Uncensored.html",
        "/en/vod/show/by/hits/id/Uncensored.html",
        "/en/javtype/Uncensored",
    ]},
    {"type_id": "reduce", "type_name": "无码破解", "paths": [
        "/en/javtype/Mosaic_Removal.html",
        "/en/vod/show/by/hits/id/Mosaic_Removal.html",
        "/en/javtype/Reduce.html",
        "/en/vod/show/by/hits/id/Reduce.html",
    ]},
    {"type_id": "chinese", "type_name": "中文字幕", "paths": [
        "/en/javtype/Chinese-Sub.html",
        "/en/javtype/Chinese_Sub.html",
        "/en/vod/show/by/hits/id/Chinese-Sub.html",
        "/en/javtype/CHN.html",
    ]},
    {"type_id": "censored", "type_name": "有码", "paths": [
        "/en/javtype/Censored.html",
        "/en/vod/show/by/hits/id/Censored.html",
    ]},
    {"type_id": "amateur", "type_name": "素人", "paths": [
        "/en/javtype/Asian_Amateur.html",
        "/en/javtype/Amateur.html",
        "/en/vod/show/by/hits/id/Amateur.html",
    ]},
    {"type_id": "vr", "type_name": "VR", "paths": [
        "/en/javtype/VR.html",
        "/en/vod/show/by/hits/id/VR.html",
        "/en/genres/vr.html",
    ]},
    {"type_id": "idol", "type_name": "女优", "paths": [
        "/en/javtype/Idol.html",
        "/en/vod/show/by/hits/id/Idol.html",
    ]},
    {"type_id": "big-tits", "type_name": "巨乳", "paths": [
        "/en/javtype/Big_Tits.html",
        "/en/genres/big_tits.html",
        "/en/vod/show/by/hits/id/Big_Tits.html",
    ]},
    {"type_id": "anal", "type_name": "肛交", "paths": [
        "/en/javtype/Anal.html",
        "/en/genres/anal.html",
        "/en/vod/show/by/hits/id/Anal.html",
    ]},
    {"type_id": "creampie", "type_name": "中出", "paths": [
        "/en/javtype/Creampie.html",
        "/en/genres/creampie.html",
        "/en/vod/show/by/hits/id/Creampie.html",
    ]},
    {"type_id": "lesbian", "type_name": "女同", "paths": [
        "/en/javtype/Lesbian.html",
        "/en/genres/lesbian.html",
        "/en/vod/show/by/hits/id/Lesbian.html",
    ]},
    {"type_id": "mature", "type_name": "熟女", "paths": [
        "/en/javtype/Mature.html",
        "/en/genres/mature.html",
        "/en/vod/show/by/hits/id/Mature.html",
    ]},
    {"type_id": "teen", "type_name": "少女", "paths": [
        "/en/javtype/Teen.html",
        "/en/genres/teen.html",
        "/en/vod/show/by/hits/id/Teen.html",
    ]},
]


class Spider(BaseSpider):
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
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Referer': self.host + '/en/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'identity',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        }
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        # Cookie 持久化，利于过 CF / 会话
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj),
            urllib.request.HTTPSHandler(context=self._ssl_context),
        )

    def _get(self, url, params=None):
        try:
            if params:
                qs = urllib.parse.urlencode(params)
                url = url + ('&' if '?' in url else '?') + qs
            req = urllib.request.Request(url, headers=self.headers, method='GET')
            resp = self._opener.open(req, timeout=18)
            raw = resp.read()
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('utf-8', errors='ignore')
        except Exception as e:
            print('_get error: %s -> %s' % (url, e), file=sys.stderr)
            return ''

    def _abs(self, u):
        if not u:
            return ''
        u = u.strip().replace('\\/', '/')
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        if not u.startswith('http'):
            return urllib.parse.urljoin(self.host + '/', u)
        return u

    def _parse_list(self, html):
        if not html or len(html) < 400:
            return []
        # CF 挑战页直接跳过
        if 'Just a moment' in html or 'cf-browser-verification' in html or 'challenge-platform' in html:
            return []

        videos = []
        seen = set()

        # 模式1：卡片（href + title/alt + 封面）
        pattern1 = re.compile(
            r'href=["\']([^"\']*(?:/jav/|/v/|/video/|/watch/|[A-Za-z0-9]{2,15}-\d{2,6}|[a-f0-9]{16,})[^"\']*)["\']'
            r'[^>]{0,500}'
            r'(?:title|alt)=["\']([^"\']{2,200})["\']'
            r'[\s\S]{0,1200}?'
            r'(?:src|data-src|data-original|data-poster|data-lazy)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            re.I
        )
        for m in pattern1.finditer(html):
            href = m.group(1).strip()
            title = (m.group(2) or '').strip()
            pic = (m.group(3) or '').strip()
            if not href or href in seen:
                continue
            if any(x in href.lower() for x in (
                'javascript:', 'mailto:', '#', '/tag/', '/category/', '/actor/',
                '/genres/', '/maker/', '/actresses/', '/vod/search'
            )):
                continue
            seen.add(href)
            if not title or len(title) < 2:
                code = re.search(r'([A-Za-z]{2,12}-\d{2,6})', href + ' ' + title)
                title = code.group(1) if code else href.rstrip('/').split('/')[-1][:50]
            vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
            videos.append({
                'vod_id': vid,
                'vod_name': re.sub(r'\s+', ' ', title)[:120],
                'vod_pic': self._abs(pic),
                'vod_remarks': ''
            })

        # 模式2：标题在 a 内
        if len(videos) < 6:
            pattern2 = re.compile(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*(?:<[^>]+>)*\s*([^<]{5,150}?)\s*<',
                re.I
            )
            for m in pattern2.finditer(html):
                href, title = m.group(1).strip(), m.group(2).strip()
                if not re.search(r'/jav/|/v/|/video/|/watch/|[A-Za-z]{2,12}-\d{2,6}|[a-f0-9]{16,}', href, re.I):
                    continue
                if href in seen or len(title) < 4:
                    continue
                if any(x in href.lower() for x in ('javascript:', 'mailto:', '#', '/vod/search')):
                    continue
                seen.add(href)
                vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
                videos.append({
                    'vod_id': vid,
                    'vod_name': re.sub(r'\s+', ' ', title)[:120],
                    'vod_pic': '',
                    'vod_remarks': ''
                })

        # 模式3：仅 /en/jav/xxx 链接
        if len(videos) < 4:
            for m in re.finditer(r'href=["\']((?:https?://[^"\']+)?/en/jav/[^"\']+)["\']', html, re.I):
                href = m.group(1).strip()
                if href in seen:
                    continue
                seen.add(href)
                vid = href if href.startswith('http') else urllib.parse.urljoin(self.host, href)
                name = href.rstrip('/').split('/')[-1].replace('.html', '')[:40]
                videos.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': ''
                })

        return videos

    def _label_from_url(self, u):
        ul = u.lower()
        if '.m3u8' in ul:
            if '1080' in ul or 'fhd' in ul or 'fullhd' in ul:
                return '1080P'
            if '720' in ul:
                return '720P'
            if '480' in ul:
                return '480P'
            if '360' in ul:
                return '360P'
            return 'HLS'
        if '1080' in ul or 'fhd' in ul:
            return '1080P'
        if '720' in ul:
            return '720P'
        if '480' in ul:
            return '480P'
        if '360' in ul:
            return '360P'
        return '播放'

    def _extract_play_urls(self, html, page_url=''):
        play_list = []
        seen = set()

        def add(u, label=None):
            if not u:
                return
            u = u.replace('\\/', '/').replace('&amp;', '&').replace('\\u0026', '&').strip()
            u = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), u)
            if not u.startswith('http') or u in seen:
                return
            if any(x in u.lower() for x in ('.js', '.css', '.png', '.jpg', '.gif', 'google', 'facebook', 'analytics')):
                return
            seen.add(u)
            if not label:
                label = self._label_from_url(u)
            play_list.append((label, u))

        if not html:
            return play_list

        for m in re.finditer(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', html, re.I):
            add(m.group(0), self._label_from_url(m.group(0)))
        for m in re.finditer(r'https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', html, re.I):
            add(m.group(0), self._label_from_url(m.group(0)))

        for m in re.finditer(r'<(?:source|video)[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html, re.I):
            add(self._abs(m.group(1)))

        js_keys = (
            'url', 'src', 'file', 'video', 'playurl', 'playUrl', 'videoUrl', 'video_url',
            'hls', 'm3u8', 'source', 'sources', 'stream', 'play_url', 'link', 'path',
            'hlsUrl', 'mp4Url', 'mediaUrl', 'contentUrl'
        )
        for key in js_keys:
            for m in re.finditer(
                rf'["\']?{key}["\']?\s*[:=]\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
                html, re.I
            ):
                add(m.group(1))
            for m in re.finditer(
                rf'\b{key}\s*=\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
                html, re.I
            ):
                add(m.group(1))

        for m in re.finditer(
            r'["\']?(?:file|src|url)["\']?\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']'
            r'[^}]{0,80}["\']?(?:label|type|res|quality)["\']?\s*:\s*["\']([^"\']+)["\']',
            html, re.I
        ):
            add(m.group(1), m.group(2).strip() or None)
        for m in re.finditer(
            r'["\']?(?:label|type|res|quality)["\']?\s*:\s*["\']([^"\']+)["\']'
            r'[^}]{0,80}["\']?(?:file|src|url)["\']?\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            html, re.I
        ):
            add(m.group(2), m.group(1).strip() or None)

        for m in re.finditer(r'<(?:iframe|embed)[^>]+src=["\']([^"\']+)["\']', html, re.I):
            src = m.group(1)
            um = re.search(r'[?&](?:url|src|file|v)=([^&"\']+)', src)
            if um:
                real = urllib.parse.unquote(um.group(1))
                if real.startswith('http'):
                    add(real)
            elif re.search(r'\.(m3u8|mp4)', src, re.I):
                add(self._abs(src))

        def sort_key(item):
            label, u = item
            l = (label or '').upper()
            if '1080' in l or 'FHD' in l:
                return 0
            if '720' in l or 'HD' in l:
                return 1
            if 'HLS' in l or '.M3U8' in u.upper():
                return 2
            if '480' in l or 'SD' in l:
                return 3
            if '360' in l:
                return 4
            return 5

        uniq = []
        seen_u = set()
        for item in sorted(play_list, key=sort_key):
            if item[1] not in seen_u:
                seen_u.add(item[1])
                uniq.append(item)
        return uniq

    def _fetch_m3u8_variants(self, master_url):
        variants = []
        try:
            text = self._get(master_url)
            if not text or '#EXTM3U' not in text:
                return variants
            lines = text.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('#EXT-X-STREAM-INF:'):
                    res_m = re.search(r'RESOLUTION=(\d+)x(\d+)', line, re.I)
                    bw_m = re.search(r'BANDWIDTH=(\d+)', line, re.I)
                    label = None
                    if res_m:
                        h = int(res_m.group(2))
                        if h >= 1080:
                            label = '1080P'
                        elif h >= 720:
                            label = '720P'
                        elif h >= 480:
                            label = '480P'
                        else:
                            label = '%sP' % h
                    elif bw_m:
                        bw = int(bw_m.group(1))
                        if bw >= 4000000:
                            label = '1080P'
                        elif bw >= 1500000:
                            label = '720P'
                        else:
                            label = '480P'
                    if i + 1 < len(lines):
                        u = lines[i + 1].strip()
                        if u and not u.startswith('#'):
                            if not u.startswith('http'):
                                u = urllib.parse.urljoin(master_url, u)
                            variants.append((label or 'HLS', u))
                i += 1
        except Exception as e:
            print('_fetch_m3u8_variants error:', e, file=sys.stderr)
        return variants

    def _cat_urls(self, tid, pg):
        """按分类生成候选 URL（含分页）"""
        pg = int(pg or 1)
        urls = []
        info = None
        for c in CATEGORIES:
            if c['type_id'] == tid:
                info = c
                break
        paths = (info or {}).get('paths') or [f'/en/javtype/{tid}.html', f'/en/{tid}/']

        for path in paths:
            base = path if path.startswith('http') else (self.host + path)
            if pg <= 1:
                urls.append(base)
                # 常见 page 参数
                if base.endswith('.html'):
                    urls.append(base + '?page=1')
                else:
                    urls.append(base.rstrip('/') + '/')
            else:
                # 分页形式
                if base.endswith('.html'):
                    # Name.html?page=N
                    urls.append(base + ('&' if '?' in base else '?') + 'page=' + str(pg))
                    # Name-N.html
                    urls.append(re.sub(r'\.html$', '-%s.html' % pg, base))
                    # Name.html/page/N
                    urls.append(base.replace('.html', '/page/%s.html' % pg))
                else:
                    urls.append(base.rstrip('/') + '/page/%s/' % pg)
                    urls.append(base.rstrip('/') + '/?page=' + str(pg))
                    urls.append(base.rstrip('/') + '-%s/' % pg)

        # 额外通用兜底
        if tid not in ('new',):
            name = tid.replace('-', '_').title().replace('_', '_')
            for extra in [
                f'/en/javtype/{tid}.html',
                f'/en/javtype/{name}.html',
                f'/en/vod/show/by/hits/id/{tid}.html',
                f'/en/vod/show/by/time/id/{tid}.html',
                f'/en/genres/{tid}.html',
            ]:
                u = self.host + extra
                if pg > 1:
                    if u.endswith('.html'):
                        urls.append(u + '?page=' + str(pg))
                        urls.append(re.sub(r'\.html$', '-%s.html' % pg, u))
                    else:
                        urls.append(u + '?page=' + str(pg))
                else:
                    urls.append(u)

        # 去重保序
        seen = set()
        out = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def homeContent(self, filter):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in CATEGORIES]
        videos = []
        try:
            for path in ('/en/', '/', '/en/vod/search.html'):
                html = self._get(self.host + path)
                videos = self._parse_list(html)
                if len(videos) >= 6:
                    break
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

        videos = []
        for url in self._cat_urls(tid, pg):
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
            'pagecount': 9999 if len(videos) >= 8 else pg,
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

        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', html, re.I)
        if m:
            name = re.sub(r'\s*[-|].*$', '', m.group(1)).strip()
            vod['vod_name'] = name[:120] if name else '视频详情'

        m = re.search(r'(?:og:image|twitter:image)["\']?\s*(?:content|href)?=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:poster|data-poster)=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            vod['vod_pic'] = self._abs(m.group(1))

        m = re.search(r'(?:og:description|description)["\']?\s*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            vod['vod_content'] = m.group(1).strip()[:300]

        play_list = self._extract_play_urls(html, page_url)
        if len(play_list) == 1 and '.m3u8' in play_list[0][1].lower():
            variants = self._fetch_m3u8_variants(play_list[0][1])
            if variants:
                play_list = variants

        if play_list:
            parts = ['%s$%s' % (label, url) for label, url in play_list[:8]]
            vod['vod_play_url'] = '#'.join(parts)
        else:
            vod['vod_play_url'] = '播放$%s' % page_url

        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        q = urllib.parse.quote(key)
        urls = [
            f'{self.host}/en/vod/search/by/time/wd/{q}.html',
            f'{self.host}/en/vod/search/by/hits/wd/{q}.html',
            f'{self.host}/en/vod/search.html?wd={q}',
            f'{self.host}/en/vod/search/wd/{q}.html',
            f'{self.host}/search/{q}/',
            f'{self.host}/en/search/{q}/',
        ]
        if pg > 1:
            extra = []
            for u in list(urls):
                if u.endswith('.html'):
                    extra.append(u + '?page=' + str(pg))
                    extra.append(re.sub(r'\.html$', f'/page/{pg}.html', u))
                else:
                    extra.append(u.rstrip('/') + f'/page/{pg}/')
            urls = extra + urls

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
            'Referer': self.host + '/en/',
            'Origin': self.host,
        }
        play = str(id or '').strip()

        if play.startswith('http') and re.search(r'\.(m3u8|mp4|flv|mpd)(\?|$)', play, re.I):
            return {
                'parse': 0,
                'jx': '0',
                'url': play,
                'header': header
            }

        if play.startswith('http'):
            html = self._get(play)
            play_list = self._extract_play_urls(html, play)
            if len(play_list) == 1 and '.m3u8' in play_list[0][1].lower():
                variants = self._fetch_m3u8_variants(play_list[0][1])
                if variants:
                    play_list = variants
            if play_list:
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
