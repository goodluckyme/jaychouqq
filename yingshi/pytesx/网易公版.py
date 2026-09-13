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
    """网易公版影像典藏 https://public.163.com 修复分类无数据（后端API失效，改用页面HTML解析）"""
    def __init__(self):
        self.siteUrl = 'https://public.163.com'
        self.hallUrl = 'https://wp.m.163.com/163/html/newsapp/time-hall/index.html'
        self.openUrl = 'https://open.163.com'
        # 分类配置：name展示名 + filter过滤关键词
        self.channels = {
            'movie': {'name': '电影', 'filter': ['电影']},
            'doc': {'name': '纪录片', 'filter': ['纪录', '纪录片']},
            'short': {'name': '短片', 'filter': ['短片', '短']},
            'archive': {'name': '影像资料馆', 'filter': ['影像资料', '资料馆']},
            'daily': {'name': '每日精读', 'filter': ['每日精读']},
        }

        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )

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
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=15).read()

            class R:
                def __init__(self, raw_data):
                    self.text = raw_data.decode('utf-8', 'ignore')

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

    def _parse_html(self, html):
        videos, seen = [], set()
        # 优先抓取带链接+标题的视频条目
        pattern_link = re.compile(
            r'href="((?:https?://(?:public|open|wp\.m)\.163\.com)?/[^"]*(?:movie|video|film|play|detail)[^"]*)"[^>]{0,300}(?:title|alt)="([^"]+)"',
            re.I
        )
        for m in pattern_link.finditer(html or ''):
            href = self._abs(m.group(1))
            name = self._clean(m.group(2))
            if not name or href in seen:
                continue
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '公版'
            })

        # 兜底抓取h2/h3标题
        if not videos:
            pat_h = re.compile(r'<h[23][^>]*>([^<]{2,60})</h[23]>[\s\S]{0,150}?(\d{4})?')
            for m in pat_h.finditer(html or ''):
                name = self._clean(m.group(1))
                skip_list = ('电影', '纪录片', '短片', '影像资料馆', '每日精读')
                if not name or name in seen or name in skip_list:
                    continue
                seen.add(name)
                year = m.group(2) or ''
                videos.append({
                    'vod_id': name,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': f'{year} 公版'
                })

        # 填充封面图，就近匹配图片
        img_pat = re.compile(r'(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', re.I)
        pic_list = []
        for im in img_pat.finditer(html):
            pic = self._abs(im.group(1))
            if pic:
                pic_list.append(pic)
        idx = 0
        for v in videos:
            if not v['vod_pic'] and idx < len(pic_list):
                v['vod_pic'] = pic_list[idx]
                idx += 1
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_html(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        limit = 24
        all_videos = []
        try:
            tid = str(tid or 'movie')
            html = self.fetch_text(self.siteUrl + '/')
            all_videos = self._parse_html(html)
            channel_cfg = self.channels.get(tid)
            if channel_cfg:
                keywords = channel_cfg['filter']
                filtered = []
                for item in all_videos:
                    text = (item['vod_name'] + ' ' + item['vod_remarks']).lower()
                    hit = any(k in text for k in keywords)
                    if hit:
                        filtered.append(item)
                raw_videos = filtered
            else:
                raw_videos = all_videos

            start = (pg - 1) * limit
            end = start + limit
            videos = raw_videos[start:end]
            total = len(raw_videos)
            pagecount = (total + limit - 1) // limit if total > 0 else 0
        except Exception as e:
            print('获取分类内容失败: %s' % e)
            videos = []
            total = 0
            pagecount = 0

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': limit,
            'total': total
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        limit = 24
        videos = []
        try:
            q = urllib.parse.quote(key)
            html = self.fetch_text(f"{self.openUrl}/search.html?keyword={q}")
            all_items = self._parse_html(html)
            # 关键词过滤
            out = []
            for v in all_items:
                if key.lower() in v['vod_name'].lower():
                    out.append(v)
            start = (pg -1)*limit
            end = start + limit
            videos = out[start:end]
            total = len(out)
            pagecount = (total + limit -1)//limit if total else 0
        except Exception as e:
            print('搜索失败: %s' % e)
            total = 0
            pagecount = 0
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': limit,
            'total': total
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, director = vid, '', '', '公版影像', ''
        play_url_raw = ''
        try:
            if vid.startswith('http'):
                page = vid
            else:
                page = self.siteUrl + '/'
            html = self.fetch_text(page)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,100})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|poster=["\'])([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            dm2 = re.search(r'导演[:：]\s*([^<\n]+)', html or '')
            if dm2:
                director = self._clean(dm2.group(1))

            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
            src = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html or '', re.I)
            src2 = re.search(r'(?:playUrl|videoUrl|mp4Url|flvUrl|src)\s*[:=]\s*["\'](https?://[^"\']+)["\']', html or '')
            if m3:
                play_url_raw = m3.group(0).replace('\\/', '/')
            elif mp4:
                play_url_raw = mp4.group(0).replace('\\/', '/')
            elif src:
                play_url_raw = self._abs(src.group(1))
            elif src2:
                play_url_raw = src2.group(1)

            final_play = play_url_raw if play_url_raw else page
            play_url = '播放$%s' % final_play
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '播放$%s' % self.siteUrl
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': '',
            'vod_director': director,
            'vod_content': (desc or '网易公版影像典藏，部分视频源站已下线。').strip(),
            'vod_play_from': '网易公版',
            'vod_play_url': play_url
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': 'https://public.163.com',
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        if play.startswith('/'):
            play = self.siteUrl + play
        html = self.fetch_text(play) if play.startswith('http') else ''
        m3 = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'jx': '0', 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        if not play.startswith('http'):
            play = self.hallUrl
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


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
    print("\n====测试分类 movie page1====")
    print(json.dumps(spider.categoryContent("movie",1,None,None), ensure_ascii=False, indent=2))
    print("\n====测试分类 doc page1====")
    print(json.dumps(spider.categoryContent("doc",1,None,None), ensure_ascii=False, indent=2))
#（注：内容由AI生成）
