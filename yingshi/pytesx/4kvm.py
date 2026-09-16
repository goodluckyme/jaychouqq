# -*- coding: utf-8 -*-
# 4K影视 https://www.4kvm.tv/  v1.1
# 修复无播放地址：Node+WASM 签名请求 /video/play 解析 m3u8
import os
import re
import sys
import json
import ssl
import subprocess
import urllib.request
import urllib.parse
import http.cookiejar

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=''):
            pass

VERSION = '1.1.0'
HOST = 'https://www.4kvm.tv'
UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
)

# 与脚本同目录下的 wasm 辅助（可选）
_WASM_DIR_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '4kvm_wasm'),
    '/home/workdir/artifacts/4kvm_wasm',
    '/tmp',
]


class Spider(BaseSpider):
    def __init__(self):
        self.host = HOST
        self.headers = {
            'User-Agent': UA,
            'Referer': HOST + '/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj),
            urllib.request.HTTPSHandler(context=self._ssl),
        )
        self._wasm_dir = None
        for d in _WASM_DIR_CANDIDATES:
            if os.path.isfile(os.path.join(d, 'nbmovie_wasm.js')) and os.path.isfile(
                os.path.join(d, 'nbmovie_wasm_bg.wasm')
            ):
                self._wasm_dir = d
                break

    def getName(self):
        return '4K影视'

    def init(self, extend=''):
        if extend and str(extend).startswith('http'):
            self.host = str(extend).rstrip('/')
            self.headers['Referer'] = self.host + '/'

    def _get(self, url, headers=None, timeout=20):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            if hasattr(self, 'fetch'):
                try:
                    r = self.fetch(url, headers=h)
                    if isinstance(r, str):
                        return r
                    if hasattr(r, 'text'):
                        return r.text or ''
                except Exception:
                    pass
            req = urllib.request.Request(url, headers=h, method='GET')
            with self._opener.open(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', 'ignore')
        except Exception as e:
            print('_get error', url, e, file=sys.stderr)
            return ''

    def _ensure_wasm(self):
        """下载 wasm 到临时目录"""
        if self._wasm_dir:
            return self._wasm_dir
        d = '/tmp/4kvm_wasm'
        os.makedirs(d, exist_ok=True)
        js_p = os.path.join(d, 'nbmovie_wasm.js')
        bg_p = os.path.join(d, 'nbmovie_wasm_bg.wasm')
        if not os.path.isfile(js_p) or not os.path.isfile(bg_p):
            # 从站点拉最新路径
            html = self._get(self.host + '/play/ch4jdmosy')
            m = re.search(
                r'id="wasm-cfg"[^>]*data-js="([^"]+)"[^>]*data-bg="([^"]+)"', html
            ) or re.search(
                r'id="wasm-cfg"[^>]*data-bg="([^"]+)"[^>]*data-js="([^"]+)"', html
            )
            if m and 'wasm' in (m.group(1) + m.group(2)):
                js_url = m.group(1) if m.group(1).endswith('.js') else m.group(2)
                bg_url = m.group(2) if m.group(1).endswith('.js') else m.group(1)
            else:
                js_url = '/static/wasm/nbmovie_wasm.426511b7.js'
                bg_url = '/static/wasm/nbmovie_wasm_bg.d5d51939.wasm'
            if not js_url.startswith('http'):
                js_url = self.host + js_url
            if not bg_url.startswith('http'):
                bg_url = self.host + bg_url
            for url, path in ((js_url, js_p), (bg_url, bg_p)):
                data = self._get(url)
                if not data and url.endswith('.wasm'):
                    # binary
                    req = urllib.request.Request(url, headers=self.headers)
                    with self._opener.open(req, timeout=30) as resp:
                        open(path, 'wb').write(resp.read())
                else:
                    if url.endswith('.wasm'):
                        req = urllib.request.Request(url, headers=self.headers)
                        with self._opener.open(req, timeout=30) as resp:
                            open(path, 'wb').write(resp.read())
                    else:
                        open(path, 'w', encoding='utf-8').write(data)
        self._wasm_dir = d
        return d

    def _build_play_path(self, dataid, secret, quality, userlink):
        d = self._ensure_wasm()
        js_path = os.path.join(d, 'nbmovie_wasm.js')
        bg_path = os.path.join(d, 'nbmovie_wasm_bg.wasm')
        script = (
            'import { readFileSync } from "fs";'
            'import * as wasm from "file://%s";'
            'await wasm.default({ module_or_path: readFileSync("%s") });'
            'console.log(wasm.build_play_url(%s,%s,%s,%s));'
        ) % (
            js_path,
            bg_path,
            json.dumps(str(dataid)),
            json.dumps(str(secret)),
            json.dumps(str(quality or '1080')),
            json.dumps(str(userlink or '0')),
        )
        try:
            out = subprocess.check_output(
                ['node', '--input-type=module', '-e', script],
                stderr=subprocess.STDOUT,
                timeout=20,
            )
            return out.decode('utf-8', 'ignore').strip().splitlines()[-1]
        except Exception as e:
            print('wasm sign error', e, file=sys.stderr)
            return ''

    def _parse_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        pat = (
            r'<a href="(/play/([a-z0-9]+))" class="block">\s*'
            r'<div[^>]*>\s*<img[^>]+data-src="([^"]*)"[^>]*alt="([^"]*)"[\s\S]*?'
            r'<h3[^>]*>\s*([^<]+?)\s*</h3>'
        )
        for m in re.finditer(pat, html, re.I):
            path, pid, pic, alt, name = m.groups()
            if pid in seen:
                continue
            seen.add(pid)
            title = (name or alt or pid).strip()
            pic = (pic or '').replace('&amp;', '&')
            if pic.startswith('//'):
                pic = 'https:' + pic
            videos.append({
                'vod_id': path,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos

    def _extract_userlink(self, html):
        m = re.search(r"userlink:'([^']+)'", html or '')
        if m:
            return m.group(1)
        m = re.search(r'userlink:"([^"]+)"', html or '')
        if m:
            return m.group(1)
        return '0'

    def homeContent(self, filter):
        classes = [
            {'type_name': '电影', 'type_id': 'movie'},
            {'type_name': '剧集', 'type_id': 'tv'},
            {'type_name': '动漫', 'type_id': 'anime'},
        ]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'movie')
        url = '%s/%s' % (self.host, tid)
        if pg > 1:
            url += '?page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        pagecount = pg + 1 if len(videos) >= 20 else pg
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': 999999,
        }

    def searchContent(self, key, quick, pg='1'):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        url = '%s/search?q=%s' % (self.host, urllib.parse.quote(key or ''))
        if pg > 1:
            url += '&page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 24,
            'total': 999999,
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else ids
        path = str(raw)
        if path.startswith('http'):
            path = path.replace(self.host, '')
        if not path.startswith('/play/'):
            path = '/play/' + path.lstrip('/')
        url = self.host + path
        html = self._get(url)
        secret = ''
        m = re.search(r'/play/([a-z0-9]+)', path, re.I)
        if m:
            secret = m.group(1)
        userlink = self._extract_userlink(html)

        title = ''
        tm = re.search(r'<h1[^>]*>([^<]+)</h1>', html) or re.search(
            r'<title>([^<]+)</title>', html
        )
        if tm:
            title = tm.group(1).replace('-4k影视', '').strip()
            title = re.sub(r'\s*-\s*第\d+集\s*$', '', title).strip()

        pic = ''
        pm = re.search(r'data-poster="([^"]+)"', html) or re.search(
            r'property="og:image"\s+content="([^"]+)"', html
        )
        if pm:
            pic = pm.group(1).replace('&amp;', '&')

        lines = re.findall(r"lineName:\s*'([^']+)'\s*,\s*episodeCount:\s*(\d+)", html)
        if not lines:
            lines = [('默认', '1')]

        ep_map = {}
        for m in re.finditer(
            r'data-line="(\d+)"[^>]*data-episode="(\d+)"\s+dataid="(\d+)"', html
        ):
            ep_map.setdefault(m.group(1), []).append((int(m.group(2)), m.group(3)))

        play_from = []
        play_urls = []
        for idx, (line_name, ep_count) in enumerate(lines, start=1):
            play_from.append(line_name)
            eps = ep_map.get(str(idx), [])
            parts = []
            if eps:
                for ep_i, dataid in sorted(eps, key=lambda x: x[0]):
                    parts.append(
                        '第%d集$%s|%s|%s|%d' % (ep_i, dataid, secret, userlink, ep_i)
                    )
            else:
                for i in range(1, max(int(ep_count), 1) + 1):
                    parts.append('第%d集$%s?line=%d&ep=%d' % (i, path, idx, i))
            play_urls.append('#'.join(parts))

        return {
            'list': [{
                'vod_id': path,
                'vod_name': title or path,
                'vod_pic': pic,
                'vod_content': title,
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_urls),
            }]
        }

    def _resolve_m3u8(self, dataid, secret, userlink, quality='1080'):
        path = self._build_play_path(dataid, secret, quality, userlink)
        if not path:
            return []
        url = path if path.startswith('http') else (self.host + path)
        # 先访问详情拿 cookie
        self._get(self.host + '/play/' + secret)
        body = self._get(
            url,
            headers={
                'Accept': 'application/json, text/plain, */*',
                'Referer': self.host + '/play/' + secret,
            },
        )
        if not body:
            return []
        try:
            data = json.loads(body)
        except Exception:
            return []
        if data.get('code') != 200 or not data.get('data'):
            return []
        result = []
        for q in data['data'].get('quality_urls') or []:
            u = q.get('url') or ''
            if not u or u == '1' or q.get('locked'):
                continue
            if re.search(r'\.(m3u8|mp4)(\?|$)', u, re.I):
                result.append({
                    'title': q.get('title') or q.get('description') or 'HLS',
                    'url': u,
                    'vip': bool(q.get('isvip')),
                })
        return result

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': UA,
            'Referer': self.host + '/',
        }
        play = str(id or '').strip()
        # dataid|secret|userlink|ep
        if '|' in play and not play.startswith('http') and '/play/' not in play:
            segs = play.split('|')
            dataid, secret = segs[0], (segs[1] if len(segs) > 1 else '')
            userlink = segs[2] if len(segs) > 2 else '0'
            urls = self._resolve_m3u8(dataid, secret, userlink, '1080')
            free = [x for x in urls if not x.get('vip')]
            pick = (free or urls)
            if pick:
                return {'parse': 0, 'jx': 0, 'url': pick[0]['url'], 'header': header}
            return {
                'parse': 1,
                'jx': '1',
                'url': self.host + '/play/' + secret,
                'header': header,
            }

        if play.startswith('http') and re.search(r'\.(m3u8|mp4)(\?|$)', play, re.I):
            return {'parse': 0, 'jx': 0, 'url': play, 'header': header}

        if play.startswith('/'):
            play = self.host + play
        page = play.split('?')[0]
        return {
            'parse': 1,
            'jx': '1',
            'url': page if page.startswith('http') else (self.host + '/' + page.lstrip('/')),
            'header': header,
        }

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print('VERSION', VERSION, 'wasm_dir', sp._wasm_dir)
    h = sp.homeContent(False)
    print('classes', h['class'])
    hv = sp.homeVideoContent()
    print('home', len(hv.get('list') or []), [x['vod_name'][:20] for x in (hv.get('list') or [])[:3]])
    if hv.get('list'):
        d = sp.detailContent([hv['list'][0]['vod_id']])
        vod = (d.get('list') or [{}])[0]
        print('detail', vod.get('vod_name'), 'from', vod.get('vod_play_from'))
        print('play_url', (vod.get('vod_play_url') or '')[:120])
        first = (vod.get('vod_play_url') or '').split('$$$')[0].split('#')[0].split('$')[-1]
        p = sp.playerContent('x', first, [])
        print('player parse', p.get('parse'), 'url', str(p.get('url') or '')[:100])
