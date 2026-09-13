#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    """网易公版影像典藏 https://public.163.com"""

    def __init__(self):
        self.siteUrl = 'https://public.163.com'
        self.hallUrl = 'https://wp.m.163.com/163/html/newsapp/time-hall/index.html'
        self.openUrl = 'https://open.163.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        # 站点实际分类: movie(电影), doc(纪录片), ani(动画片), his(珍贵史料)
        # 每日精读使用独立的read API
        self.channels = {
            'movie': {'name': '电影'},
            'doc': {'name': '纪录片'},
            'short': {'name': '动画片'},
            'archive': {'name': '珍贵史料'},
            'daily': {'name': '每日精读'},
        }
        # type_id -> API entry_kinds 映射
        self.categoryMap = {
            'movie': 'movie',
            'doc': 'doc',
            'short': 'ani',
            'archive': 'his',
            'daily': 'read',
        }
        # API端点
        self.apiMedia = 'https://active.163.com/service/form/v1/9347/view/1618.jsonp'
        self.apiSearch = 'https://active.163.com/service/form/v1/9347/view/1619.jsonp'
        self.apiRead = 'https://active.163.com/service/form/v1/9344/view/1624.jsonp'
        self.apiVideo = 'https://so.v.163.com/mobile/getBatchOnlineVideo.do'

    def getName(self):
        return '网易公版'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=12)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=12).read()

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

    def fetch_json(self, url, params=None):
        """获取纯JSON响应"""
        resp = self.fetch(url, params=params)
        if not resp:
            return {}
        try:
            return resp.json()
        except Exception:
            text = getattr(resp, 'text', '') or ''
            m = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', text)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    return {}
            return {}

    def fetch_jsonp(self, url, params=None):
        """获取JSONP响应并解析"""
        resp = self.fetch(url, params=params)
        if not resp:
            return {}
        text = getattr(resp, 'text', '') or ''
        if not text:
            return {}
        # 尝试解析JSONP: callback({...})
        jsonp_match = re.search(r'(?:callback|JSON_CALLBACK)\((.*)\)', text, re.DOTALL)
        if jsonp_match:
            try:
                return json.loads(jsonp_match.group(1))
            except Exception:
                pass
        # 尝试直接解析JSON
        try:
            return json.loads(text)
        except Exception:
            # 尝试从文本中提取JSON
            m = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', text)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
        return {}

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.siteUrl + u
        return u.replace('http://', 'https://')

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        """首页视频 - 从电影分类获取最新视频"""
        videos = []
        try:
            data = self.fetch_jsonp(self.apiMedia, {
                'param_entry_kinds': 'movie',
                'page': 1,
                'pageSize': 24
            })
            if data and data.get('status') == 'success':
                for it in data.get('list', []):
                    v = self._map_media_item(it)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容 - 调用真实API"""
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or 'movie')
            api_key = self.categoryMap.get(tid, 'movie')

            if api_key == 'read':
                # 每日精读使用独立的read API
                data = self.fetch_jsonp(self.apiRead, {
                    'page': pg,
                    'pageSize': 24
                })
                if data and data.get('status') == 'success':
                    for it in data.get('list', []):
                        v = self._map_read_item(it)
                        if v:
                            videos.append(v)
            else:
                # 电影/纪录片/动画片/珍贵史料使用mediaData API
                data = self.fetch_jsonp(self.apiMedia, {
                    'param_entry_kinds': api_key,
                    'page': pg,
                    'pageSize': 24
                })
                if data and data.get('status') == 'success':
                    for it in data.get('list', []):
                        v = self._map_media_item(it)
                        if v:
                            videos.append(v)

        except Exception as e:
            print('获取分类内容失败: %s' % e)

        # 尝试获取总页数
        total_page = pg
        try:
            data_check = self.fetch_jsonp(self.apiMedia, {
                'param_entry_kinds': self.categoryMap.get(tid, 'movie'),
                'page': 1,
                'pageSize': 1
            })
            if data_check and data_check.get('paging'):
                total_page = data_check['paging'].get('totalPage', pg)
        except Exception:
            pass

        return {
            'list': videos,
            'page': pg,
            'pagecount': total_page,
            'limit': 24,
            'total': len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        """搜索 - 调用搜索API"""
        pg = int(pg or 1)
        videos = []
        try:
            # 使用搜索API
            data = self.fetch_jsonp(self.apiSearch, {
                'param_title': key,
                'page': pg,
                'pageSize': 24
            })
            if data and data.get('status') == 'success':
                for it in data.get('list', []):
                    v = self._map_media_item(it)
                    if v:
                        videos.append(v)

            # 兜底: 如果搜索API没结果，尝试用mediaData带param_title搜索
            if not videos:
                for kind in ['movie', 'doc', 'ani', 'his']:
                    data2 = self.fetch_jsonp(self.apiMedia, {
                        'param_entry_kinds': kind,
                        'param_title': key,
                        'page': 1,
                        'pageSize': 24
                    })
                    if data2 and data2.get('status') == 'success':
                        for it in data2.get('list', []):
                            v = self._map_media_item(it)
                            if v:
                                videos.append(v)
                    if videos:
                        break
        except Exception as e:
            print('搜索失败: %s' % e)

        return {
            'list': videos,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        """详情 - 通过vid获取视频详情和播放地址"""
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, director = vid, '', '', '公版影像', ''
        play_url = self.siteUrl

        try:
            # 如果是URL格式，提取vid
            actual_vid = vid
            if vid.startswith('http'):
                # 从URL中提取vid参数或路径
                m = re.search(r'[?&]vid=([A-Za-z0-9_]+)', vid)
                if m:
                    actual_vid = m.group(1)
                else:
                    # 尝试从页面获取vid
                    html = self.fetch_text(vid)
                    if html:
                        tm = re.search(r'<title>([^<]+)</title>', html or '')
                        if tm:
                            name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
                        # 尝试从页面提取vid
                        vid_matches = re.findall(r'"vid"\s*:\s*"([A-Za-z0-9_]+)"', html)
                        if vid_matches:
                            actual_vid = vid_matches[0]

            # 通过视频API获取播放地址
            if actual_vid and re.match(r'^[A-Za-z0-9_]+$', actual_vid):
                video_data = self.fetch_json(self.apiVideo, {'vidstr': actual_vid})
                if video_data and video_data.get('retCode') == 0:
                    video_list = video_data.get('data', {}).get('video_list', [])
                    if video_list:
                        v = video_list[0]
                        # 获取播放URL
                        m3u8_url = v.get('m3u8SdUrl', '')
                        mp4_url = v.get('sdUrl', '')
                        imgpath = v.get('imgpath', '')

                        if m3u8_url:
                            play_url = '播放$%s' % m3u8_url
                        elif mp4_url:
                            play_url = '播放$%s' % mp4_url
                        else:
                            play_url = '播放$%s' % self.siteUrl

                        # 更新封面
                        if imgpath:
                            pic = self._abs(imgpath)

            # 如果是纯vid(非URL)，尝试从mediaData获取基本信息
            if not name.startswith('http') and not pic:
                # 尝试从任意分类搜索该vid
                for kind in ['movie', 'doc', 'ani', 'his']:
                    data = self.fetch_jsonp(self.apiMedia, {
                        'param_entry_kinds': kind,
                        'page': 1,
                        'pageSize': 50
                    })
                    if data and data.get('status') == 'success':
                        for item in data.get('list', []):
                            if str(item.get('id')) == vid or item.get('vid') == vid:
                                name = item.get('title', name)
                                cover = item.get('cover_pic', '')
                                if cover:
                                    pic = self._abs(cover)
                                director = item.get('director', '')
                                desc = item.get('desc', '')
                                release = item.get('release_date', '')
                                length = item.get('film_length', '')
                                remarks = '%s %s' % (release, length) if release or length else '公版影像'
                                break
        except Exception as e:
            print('获取详情失败: %s' % e)

        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': '',
            'vod_director': director,
            'vod_content': (desc or '网易公版影像典藏，站点已停更，完整片可尝试时光放映厅。').strip(),
            'vod_play_from': '网易公版',
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 直接返回m3u8/mp4 URL"""
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': 'https://public.163.com',
        }
        play = str(id or '')
        # 提取$后面的实际URL
        if '$' in play:
            play = play.split('$', 1)[1]

        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}

        # 如果是vid，尝试通过视频API获取
        if re.match(r'^[A-Za-z0-9_]+$', play):
            video_data = self.fetch_json(self.apiVideo, {'vidstr': play})
            if video_data and video_data.get('retCode') == 0:
                video_list = video_data.get('data', {}).get('video_list', [])
                if video_list:
                    v = video_list[0]
                    m3u8_url = v.get('m3u8SdUrl', '')
                    mp4_url = v.get('sdUrl', '')
                    if m3u8_url:
                        return {'parse': 0, 'jx': '0', 'url': m3u8_url, 'header': header}
                    elif mp4_url:
                        return {'parse': 0, 'jx': '0', 'url': mp4_url, 'header': header}

        # 兜底
        if play.startswith('/'):
            play = self.siteUrl + play
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.flv', '.mpd'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    # ========== 数据映射方法 ==========

    def _map_media_item(self, it):
        """映射mediaData API返回的视频项"""
        if not isinstance(it, dict):
            return None
        vid = str(it.get('id') or it.get('vid') or '')
        name = it.get('title') or it.get('media_name') or ''
        pic = it.get('cover_pic') or it.get('cover') or ''
        # 组合备注信息
        release = it.get('release_date', '')
        length = it.get('film_length', '')
        director = it.get('director', '')
        remarks_parts = [p for p in [release, length, director] if p]
        remarks = ' / '.join(remarks_parts) if remarks_parts else ''

        if not vid and not name:
            return None

        return {
            'vod_id': vid or name,
            'vod_name': self._clean(name),
            'vod_pic': self._abs(pic),
            'vod_remarks': self._clean(remarks),
        }

    def _map_read_item(self, it):
        """映射read API(每日精读)返回的项"""
        if not isinstance(it, dict):
            return None
        media_id = str(it.get('media_id') or it.get('id') or '')
        text = it.get('text') or it.get('title') or ''
        date = it.get('date') or ''
        # 从text中提取标题(取第一行作为标题)
        title = text.split('\n')[0].strip() if text else ''
        # 移除HTML标签
        title = re.sub(r'<[^>]+>', '', title)

        if not media_id and not title:
            return None

        return {
            'vod_id': media_id or title,
            'vod_name': title or '每日精读',
            'vod_pic': '',
            'vod_remarks': date,
        }


if __name__ == '__main__':
    spider = Spider()
    import json
    print("=== homeContent ===")
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
    print("\n=== homeVideoContent ===")
    home = spider.homeVideoContent()
    print(json.dumps(home, ensure_ascii=False, indent=2))
    print("\n=== categoryContent(movie) ===")
    cat = spider.categoryContent('movie', 1, True, '')
    print(json.dumps(cat, ensure_ascii=False, indent=2))
    print("\n=== categoryContent(doc) ===")
    cat2 = spider.categoryContent('doc', 1, True, '')
    print(json.dumps(cat2, ensure_ascii=False, indent=2))
    print("\n=== categoryContent(short) ===")
    cat3 = spider.categoryContent('short', 1, True, '')
    print(json.dumps(cat3, ensure_ascii=False, indent=2))
    print("\n=== categoryContent(archive) ===")
    cat4 = spider.categoryContent('archive', 1, True, '')
    print(json.dumps(cat4, ensure_ascii=False, indent=2))
    print("\n=== categoryContent(daily) ===")
    cat5 = spider.categoryContent('daily', 1, True, '')
    print(json.dumps(cat5, ensure_ascii=False, indent=2))
