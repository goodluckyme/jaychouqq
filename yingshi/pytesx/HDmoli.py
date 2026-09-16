# -*- coding: utf-8 -*-
# HDmoli - 高品质在线影视 https://www.hdmoli.me/
# 参考 8j 结构；列表走 ajax，详情/播放解析 HTML + player_aaaa
import sys, re, json, base64, binascii
from urllib.parse import quote, unquote
from base.spider import Spider
sys.path.append('..')

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


class Spider(Spider):
    host = 'https://www.hdmoli.me'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Referer': 'https://www.hdmoli.me/',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    classes = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '纪录片'},
        {'type_id': '4', 'type_name': '动漫'},
        {'type_id': '5', 'type_name': '综艺'},
    ]

    def init(self, extend=''):
        if extend:
            extend = extend.strip().rstrip('/')
            if extend.startswith('http'):
                self.host = extend
                self.headers['Referer'] = self.host + '/'

    def getName(self):
        return 'HDmoli'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass

    def _get(self, url):
        return self.fetch(url, headers=self.headers).text

    def _get_json(self, url):
        try:
            return self.fetch(url, headers=self.headers).json()
        except Exception:
            return {}

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        try:
            html = self._get(self.host + '/')
            return {'list': self._parse_list_html(html)[:24]}
        except Exception as e:
            print('homeVideoContent', e)
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        try:
            # ajax 列表更干净
            api = f'{self.host}/index.php/ajax/data?mid=1&tid={tid}&page={pg}&limit=24'
            data = self._get_json(api)
            videos = []
            for i in (data.get('list') or []):
                pic = (i.get('vod_pic') or '').replace('&amp;', '&')
                videos.append({
                    'vod_id': str(i.get('vod_id') or ''),
                    'vod_name': i.get('vod_name') or '',
                    'vod_pic': pic,
                    'vod_remarks': i.get('vod_remarks') or '',
                    'vod_year': i.get('vod_year') or '',
                })
            if not videos:
                # 回退 show 页面
                url = f'{self.host}/show/{tid}--------{pg}---.html'
                videos = self._parse_list_html(self._get(url))
            pagecount = int(data.get('pagecount') or (pg + 1 if len(videos) >= 20 else pg))
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 24,
                'total': int(data.get('total') or 9999),
            }
        except Exception as e:
            print('categoryContent', e)
            return {'list': [], 'page': pg, 'pagecount': 0}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        try:
            url = f'{self.host}/search/-------------.html?wd={quote(key)}'
            if pg > 1:
                url = f'{self.host}/search/{quote(key)}----------{pg}---.html'
            html = self._get(url)
            videos = self._parse_list_html(html)
            return {'list': videos, 'page': pg, 'pagecount': pg + 1 if len(videos) >= 12 else pg}
        except Exception as e:
            print('searchContent', e)
            return {'list': [], 'page': pg}

    def detailContent(self, ids):
        vod_id = str(ids[0]).replace('/movie/index', '').replace('.html', '')
        try:
            html = self._get(f'{self.host}/movie/index{vod_id}.html')
            name = self._re1(r'<h1[^>]*>\s*(?:<[^>]+>)*([^<]+)', html) or ''
            name = re.sub(r'<[^>]+>', '', name).strip()
            pic = self._re1(r'data-original="([^"]+)"', html) or self._re1(r'vodlist__thumb[^>]+src="([^"]+)"', html) or ''
            pic = pic.replace('&amp;', '&')
            content = self._re1(r'剧情简介[：:]*</span>\s*([\s\S]*?)</(?:p|div)>', html) or ''
            content = re.sub(r'<[^>]+>', '', content).strip()
            year = self._re1(r'年份[：:]</span>\s*<a[^>]*>([^<]+)', html) or ''
            area = self._re1(r'地区[：:]</span>\s*<a[^>]*>([^<]+)', html) or ''
            director = self._re1(r'导演[：:]</span>\s*<a[^>]*>([^<]+)', html) or ''
            actor = self._re1(r'主演[：:]</span>([\s\S]{0,400}?)</(?:p|div|span|li)>', html) or ''
            actor = re.sub(r'<[^>]+>', '', actor).strip()
            remarks = self._re1(r'更新至[^<]{0,30}|完结|HD[^<]{0,10}', html) or ''

            # 线路名：nav-tabs
            tabs = re.findall(r'<a[^>]*href="#playlist\d+"[^>]*data-toggle="tab"[^>]*>([^<]+)</a>', html)
            if not tabs:
                tabs = re.findall(r'href="#playlist\d+"[^>]*>([^<]+)</a>', html)

            play_from = []
            play_url = []
            for idx, pane in enumerate(re.findall(
                r'<div id="playlist(\d+)"[^>]*>([\s\S]*?)</div>', html
            )):
                pid, body = pane
                eps = re.findall(
                    r'href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>',
                    body
                )
                if not eps:
                    continue
                # eps: full, vodid, sid, nid, name
                line_name = tabs[idx] if idx < len(tabs) else f'线路{eps[0][2]}'
                # 跳过纯网盘线路可选：保留，播放时返回盘链
                items = []
                for full, vid, sid, nid, ep_name in eps:
                    ep_name = ep_name.strip() or f'{nid}'
                    items.append(f'{ep_name}${vid}-{sid}-{nid}')
                if items:
                    play_from.append(line_name.strip())
                    play_url.append('#'.join(items))

            vod = {
                'vod_id': vod_id,
                'vod_name': name,
                'vod_pic': pic,
                'vod_content': content,
                'vod_year': year.strip(),
                'vod_area': area.strip(),
                'vod_director': director.strip(),
                'vod_actor': actor,
                'vod_remarks': remarks.strip() if isinstance(remarks, str) else '',
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_url),
            }
            return {'list': [vod]}
        except Exception as e:
            print('detailContent', e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        # id: vod-sid-nid
        try:
            parts = str(id).split('-')
            if len(parts) >= 3:
                play_path = f'/play/{parts[0]}-{parts[1]}-{parts[2]}.html'
            else:
                play_path = str(id)
                if not play_path.startswith('/'):
                    play_path = '/play/' + play_path
            page = self.host + play_path
            html = self._get(page)
            url, header = self._parse_player(html, page)
            if url:
                parse = 0 if self._is_direct(url) else 1
                return {
                    'jx': '0',
                    'parse': str(parse),
                    'url': url,
                    'header': header,
                }
            # 回退嗅探播放页
            return {
                'jx': '0',
                'parse': '1',
                'url': page,
                'header': self.headers,
            }
        except Exception as e:
            print('playerContent', e)
            return {'jx': '0', 'parse': '1', 'url': id, 'header': self.headers}

    def _parse_player(self, html, page_url):
        header = dict(self.headers)
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
        if not m:
            return '', header
        blob = m.group(1)
        enc = 0
        em = re.search(r'"encrypt"\s*:\s*(\d+)', blob)
        if em:
            enc = int(em.group(1))
        # 取最后一个 url 字段（避免嵌套干扰）
        urls = re.findall(r'"url"\s*:\s*"((?:\\.|[^"\\])*)"', blob)
        raw = urls[-1] if urls else ''
        try:
            raw = raw.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass
        raw = raw.replace('\\/', '/')
        url = self._decode_play_url(enc, raw)
        # 网盘直链
        if url.startswith('http') and any(x in url for x in ['quark', 'pan.baidu', 'uc.cn', 'aliyundrive', 'alipan']):
            return url, header
        if url.startswith('http') and ('.m3u8' in url or '.mp4' in url or 'm3u8' in url):
            return url, header
        if url.startswith('http'):
            return url, header
        # encrypt3 等无法还原时，交给播放页嗅探；同时附带 artplayer 入口供部分壳尝试
        if raw and re.fullmatch(r'[0-9a-fA-F]+', raw):
            art = f'{self.host}/static/player/artplayer/?url={raw}'
            # 多数 TVBox 无法播 iframe，优先嗅探原播放页
            return page_url, header
        return url or page_url, header

    def _decode_play_url(self, enc, raw):
        if not raw:
            return ''
        if raw.startswith('http') or raw.startswith('//'):
            return ('https:' + raw) if raw.startswith('//') else raw
        u = raw
        try:
            if enc == 1:
                return unquote(u)
            if enc == 2:
                return unquote(base64.b64decode(u + '=' * ((4 - len(u) % 4) % 4)).decode('utf-8', 'ignore'))
            if enc == 3:
                # 常见变体：hex(base64(url)) 或 仅 base64
                if re.fullmatch(r'[0-9a-fA-F]+', u) and len(u) % 2 == 0:
                    try:
                        b64 = binascii.unhexlify(u).decode('ascii', 'ignore')
                        pad = '=' * ((4 - len(b64) % 4) % 4)
                        dec = base64.b64decode(b64 + pad)
                        try:
                            t = dec.decode('utf-8')
                            if t.startswith('http') or t.startswith('/'):
                                return t
                        except Exception:
                            pass
                    except Exception:
                        pass
                try:
                    pad = '=' * ((4 - len(u) % 4) % 4)
                    t = base64.b64decode(u + pad).decode('utf-8', 'ignore')
                    if t.startswith('http'):
                        return t
                except Exception:
                    pass
        except Exception as e:
            print('decode', e)
        return u

    def _is_direct(self, url):
        if not url or not str(url).startswith('http'):
            return False
        u = str(url).lower()
        if any(x in u for x in ['.m3u8', '.mp4', '.flv', '.mkv']):
            return True
        if any(x in u for x in ['quark.cn', 'pan.baidu', 'uc.cn', 'aliyundrive', 'alipan.com']):
            return True
        # 播放页本身不算直链
        if '/play/' in u and 'hdmoli' in u:
            return False
        return False

    def _parse_list_html(self, html):
        videos = []
        # myui-vodlist 卡片
        for m in re.finditer(
            r'<a[^>]+class="[^"]*myui-vodlist__thumb[^"]*"[^>]+href="(/movie/index(\d+)\.html)"[^>]+title="([^"]*)"[^>]*(?:data-original="([^"]*)")?',
            html
        ):
            path, vid, title, pic = m.group(1), m.group(2), m.group(3), m.group(4) or ''
            # remarks 附近
            tail = html[m.end():m.end() + 400]
            remarks = self._re1(r'pic-text[^>]*>([^<]+)', tail) or self._re1(r'pic-tag[^>]*>([^<]+)', tail) or ''
            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': (pic or '').replace('&amp;', '&'),
                'vod_remarks': remarks.strip(),
            })
        if videos:
            return videos
        # 宽松回退
        for m in re.finditer(r'href="(/movie/index(\d+)\.html)"[^>]*title="([^"]+)"', html):
            videos.append({
                'vod_id': m.group(2),
                'vod_name': m.group(3),
                'vod_pic': '',
                'vod_remarks': '',
            })
        return videos

    def _re1(self, pat, text, flags=0):
        m = re.search(pat, text, flags)
        return m.group(1).strip() if m else ''
