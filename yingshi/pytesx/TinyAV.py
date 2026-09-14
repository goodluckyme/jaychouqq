# -*- coding: utf-8 -*-
# TinyAV https://tinyavideo.com
# 模板参考: 爱奇艺.py
import re
import json
import sys
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""):
            pass

try:
    import requests
except ImportError:
    requests = None


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://tinyavideo.com'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        # type_id -> path
        self.channels = {
            'japanese': {'name': '日本AV', 'path': '/japanese/release'},
            'asian': {'name': '亞洲AV', 'path': '/asian/release'},
            'uncensored': {'name': '無碼流出', 'path': '/uncensored-leak/release'},
            'fc2': {'name': 'FC2', 'path': '/fc2/release'},
            'chinese': {'name': '中文字幕', 'path': '/chinese-subtitles'},
            'hentai': {'name': '動畫H', 'path': '/hentai/release'},
            'western': {'name': '歐美', 'path': '/western/release'},
            'korean': {'name': '韓國', 'path': '/korean/release'},
            'special': {'name': '精選片單', 'path': '/special'},
            'jp-hot': {'name': '日本熱門', 'path': '/japanese/today-hot'},
            'uc-hot': {'name': '無碼熱門', 'path': '/uncensored-leak/today-hot'},
            'fc2-hot': {'name': 'FC2熱門', 'path': '/fc2/today-hot'},
        }

    def getName(self):
        return 'TinyAV'

    def init(self, extend=""):
        if extend:
            try:
                conf = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else {}
                if conf.get('host'):
                    self.host = conf['host'].rstrip('/')
            except Exception:
                pass

    def _headers(self, referer=None):
        return {
            'User-Agent': self.ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': referer or (self.host + '/'),
        }

    def _get(self, url, referer=None):
        try:
            if requests is None:
                import urllib.request
                req = urllib.request.Request(url, headers=self._headers(referer))
                with urllib.request.urlopen(req, timeout=18) as resp:
                    return resp.read().decode('utf-8', 'ignore')
            r = requests.get(url, headers=self._headers(referer), timeout=18, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception as e:
            print('GET error', url, e)
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
            return self.host + '/' + u
        return u

    def _parse_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in re.finditer(r'href="(/video/[^"?#]+)"', html):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            block = html[max(0, m.start() - 300):m.end() + 500]
            title = ''
            tm = re.search(r'(?:title|alt)=["\']([^"\']{3,150})["\']', block)
            if tm:
                title = tm.group(1).strip()
            if not title:
                # 链接文本
                tm = re.search(r'>\s*([^<]{3,100})\s*<', block[block.find(href):block.find(href) + 200] if href in block else '')
                if tm:
                    title = tm.group(1).strip()
            if not title:
                title = href.rstrip('/').split('/')[-1]
            pic = ''
            pm = re.search(
                r'(?:src|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                block, re.I
            )
            if pm:
                pic = self._abs(pm.group(1))
            videos.append({
                'vod_id': href,
                'vod_name': title[:100],
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'list': []}

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'japanese')
        info = self.channels.get(tid, {'path': '/japanese/release'})
        path = info.get('path', '/japanese/release')
        if pg <= 1:
            url = self.host + path
        else:
            sep = '&' if '?' in path else '?'
            url = self.host + path + sep + 'page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        pagecount = pg
        if re.search(r'[?&]page=%d\b' % (pg + 1), html) or '下一頁' in html or 'next' in html.lower():
            pagecount = pg + 1
        elif len(videos) >= 10:
            pagecount = pg + 1
        # 最大页
        mx = re.findall(r'[?&]page=(\d+)', html)
        if mx:
            try:
                pagecount = max(pagecount, max(int(x) for x in mx if int(x) < 100000))
            except Exception:
                pass
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': 9999,
        }

    def detailContent(self, ids):
        result = {'list': []}
        if not ids:
            return result
        vid = str(ids[0])
        page_url = vid if vid.startswith('http') else self._abs(vid)
        html = self._get(page_url)
        if not html:
            return result

        name = ''
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = re.sub(r'\s*[|｜].*$', '', m.group(1)).strip()

        pic = ''
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'<video[^>]+poster=["\']([^"\']+)["\']', html, re.I)
        if m:
            pic = self._abs(m.group(1))

        desc = ''
        m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            desc = m.group(1).strip()[:500]

        # 播放地址
        play_urls = []
        m3u8s = self._extract_plays(html)
        if m3u8s:
            for i, u in enumerate(m3u8s):
                lab = '播放' if len(m3u8s) == 1 else ('線路%d' % (i + 1))
                # 从 URL 猜分辨率
                if '1080' in u:
                    lab = '1080P'
                elif '720' in u:
                    lab = '720P'
                play_urls.append('%s$%s' % (lab, u))
        else:
            play_urls.append('網頁播放$%s' % page_url)

        vod = {
            'vod_id': vid,
            'vod_name': name or '影片',
            'vod_pic': pic,
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': desc,
            'vod_play_from': 'TinyAV',
            'vod_play_url': '#'.join(play_urls),
        }
        result['list'] = [vod]
        return result

    def _extract_plays(self, html):
        urls = []
        seen = set()
        # JSON-LD contentUrl
        for m in re.finditer(r'"contentUrl"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', html):
            u = m.group(1).replace('\\/', '/').replace('\\u0026', '&')
            if u not in seen:
                seen.add(u)
                urls.append(u)
        # 通用 m3u8
        for m in re.finditer(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html):
            u = m.group(1).replace('\\u0026', '&')
            if u not in seen:
                seen.add(u)
                urls.append(u)
        for m in re.finditer(r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)', html):
            u = m.group(1)
            if u not in seen and 'ad' not in u.lower():
                seen.add(u)
                urls.append(u)
        return urls

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        key = (key or '').strip()
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        url = self.host + '/?s=' + quote(key)
        if pg > 1:
            url += '&page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        play = str(id or '').strip()
        if play.startswith('http') and re.search(r'\.(m3u8|mp4)(\?|$)', play, re.I):
            return {'parse': 0, 'url': play, 'header': header}
        if play.startswith('http'):
            html = self._get(play)
            plays = self._extract_plays(html)
            if plays:
                return {'parse': 0, 'url': plays[0], 'header': header}
            return {'parse': 1, 'jx': '1', 'url': play, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|ts)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print('classes', [c['type_name'] for c in sp.homeContent(False)['class']])
    print('homeVod', len(sp.homeVideoContent().get('list') or []))
    c = sp.categoryContent('japanese', 1, False, {})
    print('cat', len(c.get('list') or []), [x['vod_name'][:30] for x in (c.get('list') or [])[:3]])
    if c.get('list'):
        d = sp.detailContent([c['list'][0]['vod_id']])
        print('detail', d['list'][0]['vod_name'] if d.get('list') else None)
        print('play', (d['list'][0].get('vod_play_url') or '')[:120] if d.get('list') else None)
        if d.get('list') and d['list'][0].get('vod_play_url'):
            first = d['list'][0]['vod_play_url'].split('#')[0].split('$')[-1]
            p = sp.playerContent('TinyAV', first, [])
            print('player', p.get('parse'), (p.get('url') or '')[:90])
    s = sp.searchContentPage('FNS', False, 1)
    print('search', len(s.get('list') or []), [x['vod_name'][:30] for x in (s.get('list') or [])[:3]])
