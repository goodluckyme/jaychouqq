# coding: utf-8
"""
JAV.SB Spider  v1.6.0
修复：Cloudflare 导致无法加载分类数据
策略：优先 jav.sb，遇 CF/403 自动切换 123av.com 镜像
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

VERSION = '1.6.0'

# 主站 + 备用镜像（结构兼容解析）
HOSTS = [
    'https://jav.sb',
    'https://123av.com',
]

# type_id -> (jav.sb path, 123av path)
CATEGORIES = [
    {"type_id": "new", "type_name": "最近更新",
     "sb": "/en/label/new/by/time.html", "av": "/en"},
    {"type_id": "uncensored", "type_name": "无码",
     "sb": "/en/javtype/Uncensored.html", "av": "/en/uncensored"},
    {"type_id": "reduce", "type_name": "无码破解",
     "sb": "/en/javtype/Mosaic_Removed.html", "av": "/en/uncensored-leaked"},
    {"type_id": "chinese", "type_name": "中文字幕",
     "sb": "/en/javtype/CHN_SUB.html", "av": "/en/chinese-subtitle"},
    {"type_id": "censored", "type_name": "有码",
     "sb": "/en/javtype/Censored.html", "av": "/en/censored"},
    {"type_id": "fc2", "type_name": "FC2-PPV",
     "sb": "/en/javtype/FC2-PPV.html", "av": "/en/fc2"},
    {"type_id": "amateur", "type_name": "素人",
     "sb": "/en/javtype/Asian_Amateur.html", "av": "/en/amateur"},
    {"type_id": "vr", "type_name": "VR",
     "sb": "/en/javtype/VR.html", "av": "/en/vr"},
    {"type_id": "big-tits", "type_name": "巨乳",
     "sb": "/en/javtype/Big_Tits.html", "av": "/en/genres/big-tits"},
    {"type_id": "anal", "type_name": "肛交",
     "sb": "/en/javtype/Anal.html", "av": "/en/genres/anal"},
    {"type_id": "creampie", "type_name": "中出",
     "sb": "/en/javtype/Creampie.html", "av": "/en/genres/creampie"},
    {"type_id": "lesbian", "type_name": "女同",
     "sb": "/en/javtype/Lesbian.html", "av": "/en/genres/lesbian"},
    {"type_id": "mature", "type_name": "熟女",
     "sb": "/en/javtype/Mature.html", "av": "/en/genres/mature"},
    {"type_id": "teen", "type_name": "少女",
     "sb": "/en/javtype/Teen.html", "av": "/en/genres/teen"},
]


class Spider(BaseSpider):
    def getName(self):
        return "JAV.SB"

    def init(self, extend=""):
        self.host = HOSTS[0]
        self._mode = 'sb'  # sb | av
        if extend:
            try:
                conf = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else (extend if isinstance(extend, dict) else {})
                if conf.get('host'):
                    self.host = conf['host'].rstrip('/')
            except Exception:
                pass

        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
            'Accept-Encoding': 'identity',
            'Cache-Control': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
        }
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj),
            urllib.request.HTTPSHandler(context=self._ssl),
        )
        # 探测可用主机
        self._pick_host()

    def _pick_host(self):
        """选择能返回真实内容的主机"""
        for h in HOSTS:
            html = self._raw_get(h + '/en')
            if self._is_ok(html):
                self.host = h
                self._mode = 'av' if '123av' in h else 'sb'
                self.headers['Referer'] = self.host + '/en/'
                print('use host:', self.host, 'mode:', self._mode, file=sys.stderr)
                return
        # 默认 123av（当前环境 jav.sb 被 CF 拦）
        self.host = 'https://123av.com'
        self._mode = 'av'
        self.headers['Referer'] = self.host + '/en/'
        print('fallback host:', self.host, file=sys.stderr)

    def _is_ok(self, html):
        if not html or len(html) < 800:
            return False
        if 'Just a moment' in html or 'cf-browser-verification' in html:
            return False
        if 'challenge-platform' in html or 'Turnstile' in html:
            return False
        if '请验证' in html or 'Please verify' in html:
            return False
        # 有视频链接才算成功
        if '/en/jav/' in html or '/en/v/' in html:
            return True
        return False

    def _raw_get(self, url):
        try:
            headers = dict(self.headers)
            headers['Referer'] = self.host + '/en/'
            req = urllib.request.Request(url, headers=headers, method='GET')
            resp = self._opener.open(req, timeout=18)
            raw = resp.read()
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('utf-8', errors='ignore')
        except Exception as e:
            print('_get error:', url, e, file=sys.stderr)
            return ''

    def _get(self, url):
        html = self._raw_get(url)
        if self._is_ok(html):
            return html
        # 当前 host 失败则尝试切换
        if self._mode == 'sb':
            for h in HOSTS:
                if h == self.host:
                    continue
                alt = url.replace(self.host, h)
                # 路径映射 sb -> av
                if '123av' in h:
                    alt = self._map_url_to_av(url)
                html2 = self._raw_get(alt) if alt else ''
                if self._is_ok(html2):
                    self.host = h
                    self._mode = 'av'
                    self.headers['Referer'] = self.host + '/en/'
                    return html2
        return html

    def _map_url_to_av(self, url):
        """把 jav.sb URL 粗映射到 123av"""
        path = urllib.parse.urlparse(url).path
        # 详情
        m = re.search(r'/en/jav/([^/]+)\.html', path)
        if m:
            slug = re.sub(r'-?\d+-\d+\.html$', '', m.group(1))
            slug = re.sub(r'-\d+$', '', m.group(1))
            # 简化：用完整 slug
            return self.host + '/en/v/' + m.group(1).replace('.html', '')
        for c in CATEGORIES:
            if c['sb'] and c['sb'] in path:
                return self.host + (c['av'] or '/en')
        if '/vod/search' in path:
            m = re.search(r'/wd/([^/.]+)', path)
            if m:
                return self.host + '/en/search?keyword=' + m.group(1)
        return self.host + '/en'

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
        pg = int(pg or 1)
        info = None
        for c in CATEGORIES:
            if c['type_id'] == str(tid):
                info = c
                break
        if self._mode == 'av':
            path = (info or {}).get('av') or '/en'
            if pg <= 1:
                return self.host + path
            sep = '&' if '?' in path else '?'
            return self.host + path + sep + 'page=%d' % pg
        # jav.sb
        path = (info or {}).get('sb') or '/en/'
        if path.endswith('.html'):
            base = path[:-5]
            if pg <= 1:
                return self.host + path
            return self.host + base + '-%d.html' % pg
        if pg <= 1:
            return self.host + path
        return self.host + path + ('&' if '?' in path else '?') + 'page=%d' % pg

    def _parse_list(self, html):
        if not self._is_ok(html) and not html:
            return []
        videos = []
        seen = set()

        # 模式 A: /en/jav/xxx.html (jav.sb)
        for m in re.finditer(
            r'href=["\'](/en/jav/[^"\']+\.html)["\'][^>]*>\s*([^<]{3,200}?)\s*<',
            html, re.I
        ):
            href, title = m.group(1).strip(), re.sub(r'\s+', ' ', m.group(2).strip())
            if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', title):
                continue
            if href in seen:
                continue
            seen.add(href)
            if len(title) < 3:
                title = href.rstrip('/').split('/')[-1][:60]
            videos.append({
                'vod_id': self._abs(href),
                'vod_name': title[:150],
                'vod_pic': '',
                'vod_remarks': '',
            })

        # 模式 B: /en/v/xxx (123av)
        if len(videos) < 6:
            for m in re.finditer(
                r'href=["\'](/en/v/[^"\']+)["\']',
                html, re.I
            ):
                href = m.group(1).strip().split('?')[0]
                if href in seen:
                    continue
                # 标题：优先 alt/title，否则用 slug
                title = ''
                block = html[max(0, m.start() - 200):m.start() + 500]
                tm = re.search(r'(?:title|alt)=["\']([^"\']{3,200})["\']', block, re.I)
                if tm:
                    title = tm.group(1).strip()
                if not title:
                    # 后面文本
                    tm = re.search(
                        re.escape(href) + r'["\'][^>]*>\s*([^<]{3,150})',
                        html[m.start():m.start() + 400], re.I
                    )
                    if tm:
                        title = tm.group(1).strip()
                if not title or re.match(r'^\d{1,2}:\d{2}', title):
                    title = href.rstrip('/').split('/')[-1].replace('-', ' ').upper()
                seen.add(href)
                # 封面
                pic = ''
                pm = re.search(
                    r'(?:src|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                    block, re.I
                )
                if pm:
                    pic = self._abs(pm.group(1))
                videos.append({
                    'vod_id': self._abs(href),
                    'vod_name': re.sub(r'\s+', ' ', title)[:150],
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        # 补封面 (jav.sb)
        for v in videos:
            if v.get('vod_pic'):
                continue
            path = urllib.parse.urlparse(v['vod_id']).path
            esc = re.escape(path)
            pm = re.search(
                esc + r'[\s\S]{0,600}?(?:src|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                html, re.I
            )
            if pm:
                v['vod_pic'] = self._abs(pm.group(1))
        return videos

    def _page_total(self, html):
        m = re.search(r'Current\s*Page\s*\d+\s*/\s*(\d+)\s*Page', html, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r'page[=/](\d+)', html, re.I)
        return 0

    def homeContent(self, filter):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in CATEGORIES]
        videos = []
        try:
            urls = [self.host + '/en', self.host + '/en/']
            if self._mode == 'sb':
                urls.append(self.host + '/en/label/new/by/time.html')
            for url in urls:
                html = self._get(url)
                videos = self._parse_list(html)
                if len(videos) >= 6:
                    break
        except Exception as e:
            print('homeContent error:', e, file=sys.stderr)
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
            # 404 的分类：回退首页
            if not videos and self._mode == 'av':
                html = self._get(self.host + '/en')
                videos = self._parse_list(html)
            total = self._page_total(html)
            if total > 0:
                pagecount = total
            elif len(videos) >= 10:
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
            'total': pagecount * 12 if videos else len(videos),
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
            'vod_play_from': 'JAV',
            'vod_play_url': '',
        }
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', html, re.I)
        if m:
            name = re.sub(r'\s*[-|—].*(?:JAV|123AV).*$', '', m.group(1), flags=re.I).strip()
            vod['vod_name'] = name[:150] or '视频详情'

        m = re.search(r'(?:og:image|twitter:image)["\']?\s*(?:content|href)?=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:poster|data-poster|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            vod['vod_pic'] = self._abs(m.group(1))

        m = re.search(r'Duration\s*:?\s*([0-9:]+)', html, re.I)
        if m:
            vod['vod_remarks'] = m.group(1)

        m = re.search(r'(?:og:description|description)["\']?\s*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            vod['vod_content'] = m.group(1).strip()[:400]

        plays = self._extract_plays(html, page_url)
        if plays:
            vod['vod_play_url'] = '#'.join(['%s$%s' % (a, b) for a, b in plays])
        else:
            vod['vod_play_url'] = '网页播放$%s' % page_url
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
            seen.add(url)
            play_list.append((label or '播放', url))

        for m in re.finditer(r'(https?://[^"\'\s<>]+?\.(?:m3u8|mp4)[^"\'\s<>]*)', html, re.I):
            u = m.group(1)
            lab = '1080P' if '1080' in u else ('720P' if '720' in u else ('480P' if '480' in u else 'HLS'))
            add(lab, u)
        for m in re.finditer(r'<(?:source|video)[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html, re.I):
            add('播放', m.group(1))
        for m in re.finditer(r'(?:url|src|file|videoUrl|play_url)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I):
            add('播放', m.group(1))
        for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
            src = m.group(1)
            if any(x in src.lower() for x in ('player', 'embed', 'video', 'play')):
                add('内嵌', src)

        # 展开 m3u8 多码率
        out = []
        for lab, u in play_list:
            if '.m3u8' in u.lower():
                vars_ = self._fetch_m3u8_variants(u)
                out.extend(vars_ if vars_ else [(lab, u)])
            else:
                out.append((lab, u))

        def sk(it):
            l = (it[0] or '').upper()
            if '1080' in l: return 0
            if '720' in l: return 1
            if 'HLS' in l: return 2
            return 3
        uniq, su = [], set()
        for it in sorted(out, key=sk):
            if it[1] not in su:
                su.add(it[1])
                uniq.append(it)
        return uniq

    def _fetch_m3u8_variants(self, master_url):
        variants = []
        try:
            text = self._raw_get(master_url)
            if not text or '#EXTM3U' not in text:
                return variants
            lines = text.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('#EXT-X-STREAM-INF:'):
                    res = re.search(r'RESOLUTION=\d+x(\d+)', line, re.I)
                    label = 'HLS'
                    if res:
                        h = int(res.group(1))
                        label = '1080P' if h >= 1080 else ('720P' if h >= 720 else ('480P' if h >= 480 else '%sP' % h))
                    if i + 1 < len(lines):
                        u = lines[i + 1].strip()
                        if u and not u.startswith('#'):
                            if not u.startswith('http'):
                                u = urllib.parse.urljoin(master_url, u)
                            variants.append((label, u))
                i += 1
        except Exception:
            pass
        return variants

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        key = (key or '').strip()
        videos = []
        pagecount = 1
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        try:
            kw = urllib.parse.quote(key)
            if self._mode == 'av':
                url = '%s/en/search?keyword=%s' % (self.host, kw)
                if pg > 1:
                    url += '&page=%d' % pg
            else:
                if pg <= 1:
                    url = '%s/en/vod/search/by/time/wd/%s.html' % (self.host, kw)
                else:
                    url = '%s/en/vod/search/by/time/wd/%s-%d.html' % (self.host, kw, pg)
            html = self._get(url)
            videos = self._parse_list(html)
            total = self._page_total(html)
            pagecount = total if total > 0 else (pg + 1 if len(videos) >= 10 else pg)
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
    print('VERSION', VERSION, 'host', sp.host, 'mode', sp._mode)
    h = sp.homeContent(False)
    print('classes', len(h['class']), 'home_list', len(h.get('list') or []))
    for tid in ['new', 'uncensored', 'censored', 'reduce']:
        r = sp.categoryContent(tid, 1, False, {})
        print(tid, 'n=', len(r.get('list') or []),
              [x.get('vod_name', '')[:40] for x in (r.get('list') or [])[:2]])
    r = sp.searchContentPage('DANDY', False, 1)
    print('search', len(r.get('list') or []),
          [x.get('vod_name', '')[:40] for x in (r.get('list') or [])[:3]])
