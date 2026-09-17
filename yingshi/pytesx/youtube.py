#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube 源 (Python / TVBox)
风格对齐爱奇艺.py：分类 + 搜索 + 详情 + 播放
使用 YouTube innertube WEB 公开接口；播放返回官方页面 parse=1
"""
import json
import re
import sys
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

sys.path.append('../../')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://www.youtube.com'
        self.innertube = 'https://www.youtube.com/youtubei/v1'
        self.api_key = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        self.client = {
            'clientName': 'WEB',
            'clientVersion': '2.20240101.00.00',
            'hl': 'zh-CN',
            'gl': 'US',
        }
        self.channels = {
            'trending': {'name': '热门', 'q': 'trending'},
            'movie': {'name': '电影', 'q': '电影 完整版'},
            'tv': {'name': '电视剧', 'q': '电视剧 全集'},
            'music': {'name': '音乐', 'q': '音乐 MV'},
            'game': {'name': '游戏', 'q': '游戏 实况'},
            'news': {'name': '新闻', 'q': '新闻 热点'},
            'sport': {'name': '体育', 'q': '体育 比赛'},
            'tech': {'name': '科技', 'q': '科技 数码'},
            'live': {'name': '直播', 'q': '直播 live'},
            'kids': {'name': '少儿', 'q': '少儿 动画'},
        }

    def getName(self):
        return 'YouTube'

    def init(self, extend=''):
        if not extend:
            return
        try:
            if isinstance(extend, str) and extend.strip().startswith('{'):
                extend = json.loads(extend)
            if isinstance(extend, dict):
                if extend.get('apiKey'):
                    self.api_key = str(extend['apiKey'])
                if extend.get('gl'):
                    self.client['gl'] = str(extend['gl'])
                if extend.get('hl'):
                    self.client['hl'] = str(extend['hl'])
        except Exception:
            pass

    def fetch(self, url, headers=None, method='GET', data=None, timeout=15):
        if requests is None:
            return None
        if headers is None:
            headers = {
                'User-Agent': self.ua,
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': self.host + '/',
            }
        try:
            if method.upper() == 'POST':
                headers = dict(headers)
                headers['Content-Type'] = 'application/json'
                headers['Origin'] = self.host
                r = requests.post(url, headers=headers, data=json.dumps(data or {}), timeout=timeout)
            else:
                r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            print('fetch fail', url, e)
            return None

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = self._search_list('trending', 1)[:24]
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        info = self.channels.get(str(tid), {'q': str(tid)})
        q = info.get('q', str(tid))
        videos = self._search_list(q, pg)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = self._search_list(key, pg)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 30,
            'total': len(videos),
        }

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        vid = re.sub(r'.*v=', '', vid)
        vid = vid.split('&')[0]
        name, pic, content, actor = vid, 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % vid, '', ''
        try:
            r = self.fetch(
                self.innertube + '/player?key=' + self.api_key,
                method='POST',
                data={'context': {'client': self.client}, 'videoId': vid},
            )
            if r is not None:
                data = r.json()
                vd = data.get('videoDetails') or {}
                name = vd.get('title') or name
                content = vd.get('shortDescription') or ''
                actor = vd.get('author') or ''
                thumbs = ((vd.get('thumbnail') or {}).get('thumbnails')) or []
                if thumbs:
                    pic = thumbs[-1].get('url') or pic
        except Exception as e:
            print('detail', e)
        watch = self.host + '/watch?v=' + vid
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_content': content,
                'vod_actor': actor,
                'vod_remarks': 'YouTube',
                'vod_play_from': 'YouTube',
                'vod_play_url': '播放$' + watch,
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '')
        if not url.startswith('http'):
            if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
                url = self.host + '/watch?v=' + url
        # 官方直链需签名，统一交给解析器
        return {
            'parse': 1,
            'jx': '1',
            'url': url,
            'header': {
                'User-Agent': self.ua,
                'Referer': self.host + '/',
                'Origin': self.host,
            },
        }

    def isVideoFormat(self, url):
        if not url or not str(url).startswith('http'):
            return False
        low = str(url).lower()
        for fmt in ('.mp4', '.m3u8', '.ts', '.mkv', '.webm'):
            if fmt in low:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    # ---------- helpers ----------
    def _search_list(self, query, pg=1):
        q = str(query or '')
        if int(pg) > 1:
            q = '%s p%s' % (q, pg)
        r = self.fetch(
            self.innertube + '/search?key=' + self.api_key,
            method='POST',
            data={'context': {'client': self.client}, 'query': q},
        )
        if r is None:
            return []
        try:
            data = r.json()
        except Exception:
            return []
        out = []
        self._walk_videos(data, out)
        return self._dedupe(out)

    def _walk_videos(self, obj, out):
        if obj is None:
            return
        if isinstance(obj, list):
            for i in obj:
                self._walk_videos(i, out)
            return
        if not isinstance(obj, dict):
            return
        node = obj.get('videoRenderer') or obj.get('gridVideoRenderer') or obj.get('compactVideoRenderer')
        if node and node.get('videoId'):
            vid = node['videoId']
            name = self._title(node.get('title')) or self._title(node.get('headline')) or vid
            pic = ''
            thumbs = ((node.get('thumbnail') or {}).get('thumbnails')) or []
            if thumbs:
                pic = thumbs[-1].get('url') or ''
            if not pic:
                pic = 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % vid
            remarks_parts = []
            for key in ('publishedTimeText', 'lengthText', 'viewCountText'):
                t = self._title(node.get(key))
                if t:
                    remarks_parts.append(t)
            out.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': ' · '.join(remarks_parts),
            })
            return
        for v in obj.values():
            self._walk_videos(v, out)

    def _title(self, node):
        if not node:
            return ''
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            if node.get('simpleText'):
                return node['simpleText']
            runs = node.get('runs')
            if isinstance(runs, list):
                return ''.join(x.get('text', '') for x in runs)
        return ''

    def _dedupe(self, items):
        seen = set()
        res = []
        for it in items:
            vid = it.get('vod_id')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            res.append(it)
        return res


if __name__ == '__main__':
    sp = Spider()
    print(json.dumps(sp.homeContent(True), ensure_ascii=False, indent=2))
    print('home videos', len(sp.homeVideoContent().get('list') or []))
    print('cat', len(sp.categoryContent('movie', 1, {}, {}).get('list') or []))
