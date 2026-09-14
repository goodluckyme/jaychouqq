#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pexels 视频 Spider  v2.0
中文站：https://www.pexels.com/zh-cn/
API：https://api.pexels.com/v1/videos/ （旧 /videos/ 兼容）
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
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://www.pexels.com'
        # 新路径优先，旧路径兼容
        self.apiBases = [
            'https://api.pexels.com/v1/videos',
            'https://api.pexels.com/videos',
        ]
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        )
        self.apiKey = ''
        # 中文分类（query 走 API，path 走中文网页兜底）
        self.channels = {
            'videos': {'name': '精选', 'path': '/zh-cn/videos/', 'query': ''},
            'nature': {'name': '自然', 'path': '/zh-cn/search/videos/nature/', 'query': 'nature'},
            'city': {'name': '城市', 'path': '/zh-cn/search/videos/city/', 'query': 'city'},
            'people': {'name': '人物', 'path': '/zh-cn/search/videos/people/', 'query': 'people'},
            'animals': {'name': '动物', 'path': '/zh-cn/search/videos/animals/', 'query': 'animals'},
            'food': {'name': '美食', 'path': '/zh-cn/search/videos/food/', 'query': 'food'},
            'travel': {'name': '旅行', 'path': '/zh-cn/search/videos/travel/', 'query': 'travel'},
            'sport': {'name': '运动', 'path': '/zh-cn/search/videos/sport/', 'query': 'sport'},
            'ocean': {'name': '海洋', 'path': '/zh-cn/search/videos/ocean/', 'query': 'ocean'},
            'night': {'name': '夜景', 'path': '/zh-cn/search/videos/night/', 'query': 'night'},
            'technology': {'name': '科技', 'path': '/zh-cn/search/videos/technology/', 'query': 'technology'},
            'business': {'name': '商务', 'path': '/zh-cn/search/videos/business/', 'query': 'business'},
            'love': {'name': '爱情', 'path': '/zh-cn/search/videos/love/', 'query': 'love'},
            'sky': {'name': '天空', 'path': '/zh-cn/search/videos/sky/', 'query': 'sky'},
        }

    def getName(self):
        return 'Pexels视频'

    def init(self, extend=""):
        if not extend:
            return
        try:
            if isinstance(extend, str) and extend.strip().startswith('{'):
                ext = json.loads(extend)
                key = ext.get('apiKey') or ext.get('key') or ''
                if key:
                    self.apiKey = str(key).strip()
            elif isinstance(extend, str) and len(extend.strip()) > 16:
                self.apiKey = extend.strip()
            elif isinstance(extend, dict):
                self.apiKey = str(extend.get('apiKey') or extend.get('key') or '').strip()
        except Exception:
            pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/zh-cn/videos/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=15).read()

            class R:
                def __init__(self, raw):
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_text(self, url, params=None):
        resp = self.fetch(url, params=params)
        return getattr(resp, 'text', '') if resp else ''

    def _api(self, path, params=None):
        """请求 API，优先 v1，无 key 时仍尝试（可能失败）"""
        params = dict(params or {})
        # 中文 locale，便于标题/相关性偏中文
        if 'locale' not in params:
            params['locale'] = 'zh-CN'
        headers = {
            'User-Agent': self.userAgent,
            'Accept': 'application/json',
        }
        if self.apiKey and len(self.apiKey) >= 16 and not re.search(r'test|xxx|your|example', self.apiKey, re.I):
            headers['Authorization'] = self.apiKey

        for base in self.apiBases:
            url = base + path
            resp = self.fetch(url, headers=headers, params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                if isinstance(data, dict) and (
                    data.get('videos') is not None
                    or data.get('video_files') is not None
                    or data.get('id') is not None
                ):
                    return data
            except Exception:
                continue
        return {}

    def _walk_videos(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if obj.get('id') and (obj.get('video_files') or obj.get('image') or obj.get('url')):
                marker = str(obj.get('url') or obj.get('type') or 'video').lower()
                if 'video' in marker or obj.get('video_files'):
                    acc.append(obj)
            for v in obj.values():
                self._walk_videos(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk_videos(v, acc)
        return acc

    def _parseVideoItem(self, item):
        vid = str(item.get('id') or '')
        url = str(item.get('url') or '')
        slug = ''
        m = re.search(r'/video/([^/?]+)', url)
        if m:
            slug = re.sub(r'-\d+$', '', m.group(1)).replace('-', ' ').strip()
        title = slug.title() if slug else ('Pexels #%s' % vid)
        user = ''
        if isinstance(item.get('user'), dict):
            user = item['user'].get('name') or ''
        elif item.get('photographer'):
            user = item.get('photographer')
        duration = item.get('duration') or 0
        pic = item.get('image') or ''
        pics = item.get('video_pictures') or []
        if not pic and pics:
            pic = (pics[0] or {}).get('picture') or ''
        remarks = ''
        if duration:
            remarks = '%ds' % int(duration)
        if user:
            remarks = (remarks + ' · ' + user) if remarks else user
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': user,
        }

    def _from_html(self, path):
        url = path if str(path).startswith('http') else self.siteUrl + path
        html = self.fetch_text(url)
        videos = []
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html or '', re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                seen = set()
                for item in self._walk_videos(data.get('props') or data):
                    v = self._parseVideoItem(item)
                    if v['vod_id'] and v['vod_id'] not in seen:
                        seen.add(v['vod_id'])
                        videos.append(v)
            except Exception as e:
                print('解析 NEXT_DATA 失败: %s' % e)
        if videos:
            return videos
        for href, name in re.findall(
            r'href="(https://www\.pexels\.com/[^"]*/video/([^"/]+))"',
            html or '',
        ):
            mid = re.search(r'-(\d+)/?$', href)
            vid = mid.group(1) if mid else name
            title = re.sub(r'-\d+$', '', name).replace('-', ' ').title()
            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': '',
                'vod_remarks': '',
            })
        return videos

    def _list(self, query, path, pg=1):
        pg = int(pg or 1)
        # 1) 官方 API
        if query:
            data = self._api('/search', {'query': query, 'page': pg, 'per_page': 24})
        else:
            data = self._api('/popular', {'page': pg, 'per_page': 24})
        items = (data or {}).get('videos') or []
        if items:
            videos = [self._parseVideoItem(x) for x in items]
            total = int(data.get('total_results') or len(videos))
            pagecount = max(1, (total + 23) // 24)
            return videos, pagecount, total

        # 2) 中文网页兜底
        page_path = path or '/zh-cn/videos/'
        if pg > 1:
            page_path = page_path.rstrip('/') + '/?page=' + str(pg)
        videos = self._from_html(page_path)
        return videos, (pg + 1 if len(videos) >= 12 else pg), len(videos)

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        result = {'class': classes}
        if filter:
            result['filters'] = {}
        return result

    def homeVideoContent(self):
        videos = []
        try:
            videos, _, _ = self._list('', '/zh-cn/videos/', 1)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos, pagecount, total = [], pg, 0
        try:
            info = self.channels.get(str(tid), self.channels['videos'])
            videos, pagecount, total = self._list(
                info.get('query') or '',
                info.get('path') or '/zh-cn/videos/',
                pg,
            )
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': total or len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos, pagecount, total = [], pg, 0
        try:
            path = '/zh-cn/search/videos/' + urllib.parse.quote(key) + '/'
            videos, pagecount, total = self._list(key, path, pg)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': total or len(videos),
        }

    def _best_file(self, item):
        files = item.get('video_files') or []
        mp4s = []
        for f in files:
            link = f.get('link') or ''
            if not link:
                continue
            ft = str(f.get('file_type') or '').lower()
            if 'mp4' not in ft and '.mp4' not in link:
                continue
            mp4s.append((int(f.get('height') or 0), f.get('quality') or '', link))
        mp4s.sort(key=lambda x: x[0], reverse=True)
        return mp4s

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        try:
            item = {}
            # API 详情：/videos/{id}
            item = self._api('/videos/' + vid) or {}
            if not item.get('id'):
                item = self._api('/' + vid) or {}
            if not item.get('id'):
                html = self.fetch_text(self.siteUrl + '/zh-cn/video/' + vid + '/')
                if not html:
                    html = self.fetch_text(self.siteUrl + '/video/' + vid + '/')
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html or '', re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        found = self._walk_videos(data)
                        for it in found:
                            if str(it.get('id')) == vid:
                                item = it
                                break
                        if not item and found:
                            item = found[0]
                    except Exception:
                        pass
                if not item.get('video_files'):
                    files = re.findall(r'https://[^"\']+\.mp4[^"\']*', html or '')
                    if files:
                        item['id'] = vid
                        item['video_files'] = [
                            {'link': u.replace('\\/', '/'), 'height': 0} for u in files
                        ]
            parsed = self._parseVideoItem(item) if item else {
                'vod_id': vid, 'vod_name': 'Pexels #%s' % vid, 'vod_pic': '', 'vod_remarks': ''
            }
            parts = []
            for h, q, link in self._best_file(item):
                label = str(h) + 'p' if h else (q or 'MP4')
                parts.append('%s$%s' % (label, link))
            if not parts:
                parts.append('网页$%s/zh-cn/video/%s/' % (self.siteUrl, vid))
            return {'list': [{
                'vod_id': vid,
                'vod_name': parsed.get('vod_name') or vid,
                'vod_pic': parsed.get('vod_pic') or '',
                'vod_remarks': parsed.get('vod_remarks') or '',
                'vod_actor': parsed.get('vod_actor') or '',
                'vod_content': 'Pexels 免费可商用素材，使用时请保留作者署名。来源：pexels.com/zh-cn',
                'vod_play_from': 'Pexels',
                'vod_play_url': '#'.join(parts),
            }]}
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
        }
        play_url = str(id or '')
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': header}
        m = re.search(r'(\d{4,})', play_url)
        vid = m.group(1) if m else play_url
        item = self._api('/videos/' + vid) or self._api('/' + vid) or {}
        files = self._best_file(item)
        if files:
            return {'parse': 0, 'url': files[0][2], 'header': header}
        html = self.fetch_text(self.siteUrl + '/zh-cn/video/' + vid + '/')
        mp4 = re.search(r'https://[^"\']+\.mp4[^"\']*', html or '')
        if mp4:
            return {'parse': 0, 'url': mp4.group(0).replace('\\/', '/'), 'header': header}
        return {
            'parse': 1,
            'jx': '0',
            'url': self.siteUrl + '/zh-cn/video/' + vid + '/',
            'header': header,
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.webm', '.mov'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
