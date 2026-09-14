# coding: utf-8
"""
JAV.SB Spider  v1.5.0
修复：分类无数据
真实结构（已验证）：
  首页     /en/
  最新     /en/label/new/by/time.html
  分类     /en/javtype/{Name}.html
  分页     /en/javtype/{Name}-{N}.html  或  ?page=N
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

VERSION = '1.5.0'
SITE_URL = 'https://jav.sb'

# type_id -> 站点真实路径（已用真实页面验证）
CATEGORIES = [
    {"type_id": "new", "type_name": "最近更新", "path": "/en/label/new/by/time.html"},
    {"type_id": "rank", "type_name": "热门排行", "path": "/en/label/rank/by/time.html"},
    {"type_id": "uncensored", "type_name": "无码", "path": "/en/javtype/Uncensored.html"},
    {"type_id": "reduce", "type_name": "无码破解", "path": "/en/javtype/Mosaic_Removed.html"},
    {"type_id": "chinese", "type_name": "中文字幕", "path": "/en/javtype/CHN_SUB.html"},
    {"type_id": "censored", "type_name": "有码", "path": "/en/javtype/Censored.html"},
    {"type_id": "fc2", "type_name": "FC2-PPV", "path": "/en/javtype/FC2-PPV.html"},
    {"type_id": "amateur", "type_name": "素人", "path": "/en/javtype/Asian_Amateur.html"},
    {"type_id": "vr", "type_name": "VR", "path": "/en/javtype/VR.html"},
    {"type_id": "idol", "type_name": "女优", "path": "/en/javtype/Idol.html"},
    {"type_id": "big-tits", "type_name": "巨乳", "path": "/en/javtype/Big_Tits.html"},
    {"type_id": "anal", "type_name": "肛交", "path": "/en/javtype/Anal.html"},
    {"type_id": "creampie", "type_name": "中出", "path": "/en/javtype/Creampie.html"},
    {"type_id": "lesbian", "type_name": "女同", "path": "/en/javtype/Lesbian.html"},
    {"type_id": "mature", "type_name": "熟女", "path": "/en/javtype/Mature.html"},
    {"type_id": "teen", "type_name": "少女", "path": "/en/javtype/Teen.html"},
    {"type_id": "mgs", "type_name": "MGS", "path": "/en/javtype/MGS.html"},
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
            resp = self._opener.open(req, timeout=20)
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

    def _cat_url(self, tid, pg=1):
        """生成分类 URL（含分页）"""
        pg = int(pg or 1)
        path = None
        for c in CATEGORIES:
            if c['type_id'] == str(tid):
                path = c.get('path')
                break
        if not path:
            path = '/en/'

        # 首页 / 标签页分页
        if path.rstrip('/').endswith('.html'):
            base = path[:-5]  # strip .html
            if pg <= 1:
                return self.host + path
            # /en/javtype/Uncensored-2.html
            return self.host + base + '-%d.html' % pg

        # 兜底
        if pg <= 1:
            return self.host + path
        return self.host + path + ('&' if '?' in path else '?') + 'page=%d' % pg

    def _parse_list(self, html):
        if not html or len(html) < 300:
            return []
        if 'Just a moment' in html or 'cf-browser-verification' in html or 'challenge-platform' in html:
            return []
        if '请验证' in html or 'Please verify' in html:
            return []

        videos = []
        seen = set()

        # 主模式：/en/jav/xxx.html + 标题
        # 兼容 duration 链接与标题链接
        pattern = re.compile(
            r'href=["\'](/en/jav/[^"\']+\.html)["\'][^>]*>\s*([^<]{3,200}?)\s*<',
            re.I
        )
        for m in pattern.finditer(html):
            href = m.group(1).strip()
            title = re.sub(r'\s+', ' ', (m.group(2) or '').strip())
            # 跳过纯时长如 1:01:30
            if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', title):
                continue
            if href in seen:
                continue
            seen.add(href)
            if len(title) < 3:
                code = re.search(r'([A-Za-z0-9]{2,15}-\d{2,6})', href)
                title = code.group(1).upper() if code else href.rstrip('/').split('/')[-1][:50]
            videos.append({
                'vod_id': self._abs(href),
                'vod_name': title[:150],
                'vod_pic': '',
                'vod_remarks': '',
            })

        # 补封面：在同卡片附近找 img
        if videos:
            for v in videos:
                slug = urllib.parse.urlparse(v['vod_id']).path
                # 在 href 附近找图片
                esc = re.escape(slug)
                m = re.search(
                    esc + r'[\s\S]{0,800}?(?:src|data-src|data-original|data-poster)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                    html, re.I
                )
                if not m:
                    m = re.search(
                        r'(?:src|data-src|data-original)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\'][\s\S]{0,800}?' + esc,
                        html, re.I
                    )
                if m:
                    v['vod_pic'] = self._abs(m.group(1))

        # 时长备注
        for v in videos:
            slug = urllib.parse.urlparse(v['vod_id']).path
            m = re.search(
                r'>(\d{1,2}:\d{2}(?::\d{2})?)<[^>]{0,200}' + re.escape(slug),
                html, re.I
            )
            if m:
                v['vod_remarks'] = m.group(1)

        return videos

    def _page_total(self, html):
        """解析 CurrentPage 1/636 Page"""
        m = re.search(r'Current\s*Page\s*\d+\s*/\s*(\d+)\s*Page', html, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r'/\s*(\d+)\s*$', html)
        return int(m.group(1)) if m else 0

    def homeContent(self, filter):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in CATEGORIES]
        videos = []
        try:
            for url in [self.host + '/en/', self.host + '/en/label/new/by/time.html']:
                html = self._get(url)
                videos = self._parse_list(html)
                if len(videos) >= 6:
                    break
        except Exception as e:
            print('homeContent list error:', e, file=sys.stderr)
        return {'class': classes, 'list': videos[:24]}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'new')
        videos = []
        pagecount = 9999
        try:
            url = self._cat_url(tid, pg)
            html = self._get(url)
            videos = self._parse_list(html)
            # 分页备用：?page=
            if len(videos) < 4 and pg > 1:
                path = None
                for c in CATEGORIES:
                    if c['type_id'] == tid:
                        path = c.get('path')
                        break
                if path:
                    alt = self.host + path + ('&' if '?' in path else '?') + 'page=%d' % pg
                    html2 = self._get(alt)
                    v2 = self._parse_list(html2)
                    if len(v2) > len(videos):
                        videos = v2
                        html = html2
            total_pages = self._page_total(html)
            if total_pages > 0:
                pagecount = total_pages
            elif len(videos) >= 8:
                pagecount = pg + 1
            else:
                pagecount = pg
        except Exception as e:
            print('categoryContent error:', e, file=sys.stderr)

        type_name = tid
        for c in CATEGORIES:
            if c['type_id'] == tid:
                type_name = c['type_name']
                break

        return {
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': pagecount * 12 if videos else 0,
            'type_name': type_name,
            'list': videos,
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
            'vod_play_url': '',
        }

        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', html, re.I)
        if m:
            name = re.sub(r'\s*[-|].*JAVSB.*$', '', m.group(1), flags=re.I).strip()
            name = re.sub(r'\s*[-|]\s*$', '', name).strip()
            vod['vod_name'] = name[:150] if name else '视频详情'

        m = re.search(r'(?:og:image|twitter:image)["\']?\s*(?:content|href)?=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:poster|data-poster)=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            vod['vod_pic'] = self._abs(m.group(1))

        m = re.search(r'Duration\s*:\s*([0-9:]+)', html, re.I)
        if m:
            vod['vod_remarks'] = m.group(1)

        m = re.search(r'(?:og:description|description)["\']?\s*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            vod['vod_content'] = m.group(1).strip()[:400]
        else:
            # 正文简介
            m = re.search(r'<h1[^>]*>[\s\S]{0,200}?</h1>\s*<p[^>]*>([\s\S]{20,500}?)</p>', html, re.I)
            if m:
                vod['vod_content'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:400]

        plays = self._extract_plays(html, page_url)
        if plays:
            vod['vod_play_url'] = '#'.join(['%s$%s' % (lab, u) for lab, u in plays])
        else:
            vod['vod_play_url'] = '网页播放$%s' % page_url
            vod['vod_play_from'] = 'JAV.SB'

        result['list'] = [vod]
        return result

    def _extract_plays(self, html, page_url):
        play_list = []
        seen = set()

        def add(label, url):
            url = (url or '').strip().replace('\\/', '/')
            if not url or url in seen:
                return
            if not url.startswith('http'):
                url = self._abs(url)
            if not re.search(r'\.(m3u8|mp4)(\?|$)', url, re.I) and 'm3u8' not in url.lower():
                # 仍可能是播放器接口
                if not re.search(r'(play|video|stream|player|m3u)', url, re.I):
                    return
            seen.add(url)
            play_list.append((label or '播放', url))

        # 直接 m3u8/mp4
        for m in re.finditer(r'(https?://[^"\'\s<>]+?\.(?:m3u8|mp4)[^"\'\s<>]*)', html, re.I):
            u = m.group(1)
            lab = '1080P' if '1080' in u else ('720P' if '720' in u else ('480P' if '480' in u else 'HLS'))
            add(lab, u)

        # source/video tags
        for m in re.finditer(r'<(?:source|video)[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html, re.I):
            add('播放', m.group(1))

        # player config json
        for m in re.finditer(r'(?:url|src|file|videoUrl|video_url|play_url)\s*[:=]\s*["\']([^"\']+)["\']', html, re.I):
            add('播放', m.group(1))

        # iframe player
        for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
            src = m.group(1)
            if any(x in src.lower() for x in ('player', 'embed', 'video', 'play')):
                add('内嵌', src)

        # 展开 master m3u8 多码率
        expanded = []
        for lab, u in play_list:
            if '.m3u8' in u.lower() and 'master' not in lab.lower():
                variants = self._fetch_m3u8_variants(u)
                if variants:
                    expanded.extend(variants)
                else:
                    expanded.append((lab, u))
            else:
                expanded.append((lab, u))
        if expanded:
            play_list = expanded

        # 排序：高清优先
        def sort_key(item):
            l = (item[0] or '').upper()
            if '1080' in l:
                return 0
            if '720' in l:
                return 1
            if 'HLS' in l or 'M3U8' in (item[1] or '').upper():
                return 2
            if '480' in l:
                return 3
            return 4

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
                    label = 'HLS'
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
                    if i + 1 < len(lines):
                        u = lines[i + 1].strip()
                        if u and not u.startswith('#'):
                            if not u.startswith('http'):
                                u = urllib.parse.urljoin(master_url, u)
                            variants.append((label, u))
                i += 1
        except Exception as e:
            print('_fetch_m3u8_variants error:', e, file=sys.stderr)
        return variants

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        key = (key or '').strip()
        videos = []
        pagecount = 1
        if not key:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0}
        try:
            kw = urllib.parse.quote(key, safe='')
            if pg <= 1:
                url = '%s/en/vod/search/by/time/wd/%s.html' % (self.host, kw)
            else:
                # 搜索分页：path-N.html 或 ?page=
                url = '%s/en/vod/search/by/time/wd/%s-%d.html' % (self.host, kw, pg)
            html = self._get(url)
            videos = self._parse_list(html)
            if len(videos) < 3 and pg > 1:
                alt = '%s/en/vod/search/by/time/wd/%s.html?page=%d' % (self.host, kw, pg)
                html2 = self._get(alt)
                v2 = self._parse_list(html2)
                if len(v2) > len(videos):
                    videos = v2
                    html = html2
            total_pages = self._page_total(html)
            if total_pages > 0:
                pagecount = total_pages
            elif len(videos) >= 8:
                pagecount = pg + 1
            else:
                pagecount = pg
        except Exception as e:
            print('search error:', e, file=sys.stderr)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': pagecount * 12 if videos else len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/en/',
            'Origin': self.host,
        }
        play = str(id or '').strip()
        if play.startswith('http') and re.search(r'\.(m3u8|mp4)(\?|$)', play, re.I):
            return {'parse': 0, 'url': play, 'header': header}
        if play.startswith('http'):
            # 可能是详情页，再提取
            html = self._get(play)
            plays = self._extract_plays(html, play)
            if plays:
                return {'parse': 0, 'url': plays[0][1], 'header': header}
            return {'parse': 1, 'jx': '1', 'url': play, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|webm)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print('VERSION', VERSION)
    print('home classes', [c['type_name'] for c in sp.homeContent(False)['class']])
    for tid in ['new', 'uncensored', 'chinese', 'reduce']:
        r = sp.categoryContent(tid, 1, False, {})
        print(tid, 'n=', len(r.get('list') or []), 'pages', r.get('pagecount'),
              [x.get('vod_name', '')[:30] for x in (r.get('list') or [])[:2]])
