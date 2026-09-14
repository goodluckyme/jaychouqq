#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
光厂 VJshi 视频素材 Spider
站点：https://www.vjshi.com/
列表：/so/{关键词}.html
详情：/watch/{id}.html
说明：站点有 JS 反爬，客户端需能正常访问页面
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
        self.siteUrl = 'https://www.vjshi.com'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        )
        # 分类用搜索关键词映射
        self.channels = {
            'new': {'name': '最新', 'query': '', 'path': '/new.html'},
            'nature': {'name': '自然风景', 'query': '自然'},
            'city': {'name': '城市建筑', 'query': '城市'},
            'people': {'name': '人物生活', 'query': '人物'},
            'tech': {'name': '科技数据', 'query': '科技'},
            'business': {'name': '商务企业', 'query': '商务'},
            'medical': {'name': '医疗健康', 'query': '医疗'},
            'edu': {'name': '教育文化', 'query': '教育'},
            'food': {'name': '美食餐饮', 'query': '美食'},
            'sport': {'name': '运动健身', 'query': '运动'},
            'traffic': {'name': '交通出行', 'query': '交通'},
            'factory': {'name': '工业制造', 'query': '工厂'},
            'ae': {'name': 'AE模板', 'query': 'AE模板'},
            '4k': {'name': '4K素材', 'query': '4K'},
        }

    def getName(self):
        return '光厂视频'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=15).read()

            class R:
                def __init__(self, raw):
                    try:
                        self.text = raw.decode('utf-8')
                    except Exception:
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

    def _abs(self, u):
        if not u:
            return ''
        u = u.strip().replace('\\/', '/')
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.siteUrl + u
        if not u.startswith('http'):
            return urllib.parse.urljoin(self.siteUrl + '/', u)
        return u

    def _parse_list(self, html):
        videos = []
        if not html or len(html) < 800:
            return videos
        # 反爬页
        if 'var arg1=' in html and len(html) < 15000 and '/watch/' not in html:
            return videos
        seen = set()

        # 模式1：watch 链接 + 标题 + 封面
        # 常见：href="/watch/123.html" ... img ... title
        pattern1 = re.compile(
            r'href=["\']((?:https?://(?:www\.)?vjshi\.com)?/watch/(\d+)\.html)["\']'
            r'[\s\S]{0,1200}?'
            r'(?:src|data-src|data-original)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']'
            r'[\s\S]{0,600}?'
            r'(?:title|alt)=["\']([^"\']{2,120})["\']',
            re.I
        )
        for m in pattern1.finditer(html):
            href, vid, pic, title = m.group(1), m.group(2), m.group(3), m.group(4).strip()
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': title[:100],
                'vod_pic': self._abs(pic),
                'vod_remarks': '',
            })

        # 模式2：标题在 a 内
        if len(videos) < 6:
            pattern2 = re.compile(
                r'href=["\']((?:https?://(?:www\.)?vjshi\.com)?/watch/(\d+)\.html)["\'][^>]*>'
                r'[\s\S]{0,400}?'
                r'(?:title=["\']([^"\']+)["\']|>([^<]{4,80})<)',
                re.I
            )
            for m in pattern2.finditer(html):
                vid = m.group(2)
                if vid in seen:
                    continue
                title = (m.group(3) or m.group(4) or '').strip()
                if not title:
                    continue
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': title[:100],
                    'vod_pic': '',
                    'vod_remarks': '',
                })

        # 模式3：仅 id
        if len(videos) < 4:
            for m in re.finditer(r'/watch/(\d+)\.html', html):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': '素材 #%s' % vid,
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        return videos

    def _list_url(self, query, path, pg):
        pg = int(pg or 1)
        if path and not query:
            url = self.siteUrl + path
            if pg > 1:
                if url.endswith('.html'):
                    url = url.replace('.html', '/p%s.html' % pg)
                else:
                    url = url.rstrip('/') + '/?page=' + str(pg)
            return url
        kw = urllib.parse.quote(query or '视频')
        if pg <= 1:
            return '%s/so/%s.html' % (self.siteUrl, kw)
        return '%s/so/%s/p%s.html' % (self.siteUrl, kw, pg)

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        result = {'class': classes}
        if filter:
            result['filters'] = {}
        return result

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/new.html')
            if not html or len(html) < 1000:
                html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_list(html)
            if not videos:
                html = self.fetch_text(self._list_url('自然', '', 1))
                videos = self._parse_list(html)
        except Exception as e:
            print('首页失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        pagecount = pg
        try:
            info = self.channels.get(str(tid), {'query': str(tid), 'path': ''})
            url = self._list_url(info.get('query') or str(tid), info.get('path') or '', pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
            pagecount = pg + 1 if len(videos) >= 12 else pg
        except Exception as e:
            print('分类失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': 9999 if videos else 0,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            url = self._list_url(key, '', pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': 9999 if videos else len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        vid = re.sub(r'\D', '', vid) or vid
        try:
            url = '%s/watch/%s.html' % (self.siteUrl, vid)
            html = self.fetch_text(url)
            name = '素材 #%s' % vid
            pic = ''
            desc = ''
            remarks = ''

            m = re.search(r'<title>([^<]+)</title>', html or '', re.I)
            if m:
                name = re.sub(r'\s*[-|_].*光厂.*$', '', m.group(1)).strip() or name
            m = re.search(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html or '', re.I)
            if m:
                name = m.group(1).strip()
            m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html or '', re.I)
            if m:
                pic = self._abs(m.group(1))
            if not pic:
                m = re.search(r'(?:poster|data-poster)=["\']([^"\']+)["\']', html or '', re.I)
                if m:
                    pic = self._abs(m.group(1))
            m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html or '', re.I)
            if m:
                desc = m.group(1).strip()[:400]
            m = re.search(r'(\d+[\'′]\d+|\d+:\d+|时长[^<\d]*\d+)', html or '')
            if m:
                remarks = m.group(1)

            # 预览地址：小样 / preview mp4 / m3u8
            play_parts = []
            seen = set()
            for m in re.finditer(r'https?://[^"\'\s<>\\]+\.(?:mp4|m3u8)[^"\'\s<>\\]*', html or '', re.I):
                u = m.group(0).replace('\\/', '/')
                if u in seen:
                    continue
                if any(x in u.lower() for x in ('.js', '.css', 'google')):
                    continue
                seen.add(u)
                label = '预览'
                if '1080' in u or 'hd' in u.lower():
                    label = '1080P'
                elif '720' in u:
                    label = '720P'
                elif '480' in u or 'sd' in u.lower():
                    label = '480P'
                play_parts.append('%s$%s' % (label, u))

            # video / source 标签
            for m in re.finditer(r'<(?:video|source)[^>]+(?:src|data-src)=["\']([^"\']+)["\']', html or '', re.I):
                u = self._abs(m.group(1))
                if u and u not in seen and re.search(r'\.(mp4|m3u8)', u, re.I):
                    seen.add(u)
                    play_parts.append('播放$%s' % u)

            # JS 变量
            for key in ('url', 'src', 'file', 'videoUrl', 'playUrl', 'preview', 'sample'):
                for m in re.finditer(
                    rf'["\']?{key}["\']?\s*[:=]\s*["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                    html or '', re.I
                ):
                    u = m.group(1)
                    if u not in seen:
                        seen.add(u)
                        play_parts.append('预览$%s' % u)

            if not play_parts:
                # 无直链：交给解析器 / 网页
                play_parts.append('网页$%s' % url)

            return {'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'vod_content': desc or '光厂（VJshi）正版视频素材，完整下载需授权，此处仅预览。',
                'vod_play_from': '光厂',
                'vod_play_url': '#'.join(play_parts[:8]),
            }]}
        except Exception as e:
            print('详情失败: %s' % e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
        }
        play = str(id or '').strip()
        if play.startswith('http') and re.search(r'\.(mp4|m3u8|webm)(\?|$)', play, re.I):
            return {'parse': 0, 'url': play, 'header': header}
        # 详情页再抽一次
        if play.startswith('http'):
            html = self.fetch_text(play)
            m = re.search(r'https?://[^"\'\s<>\\]+\.(?:mp4|m3u8)[^"\'\s<>\\]*', html or '', re.I)
            if m:
                return {'parse': 0, 'url': m.group(0).replace('\\/', '/'), 'header': header}
            return {'parse': 1, 'jx': '1', 'url': play, 'header': header}
        # 纯 id
        page = '%s/watch/%s.html' % (self.siteUrl, re.sub(r'\D', '', play) or play)
        html = self.fetch_text(page)
        m = re.search(r'https?://[^"\'\s<>\\]+\.(?:mp4|m3u8)[^"\'\s<>\\]*', html or '', re.I)
        if m:
            return {'parse': 0, 'url': m.group(0).replace('\\/', '/'), 'header': header}
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(mp4|m3u8|webm|mov)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(False), ensure_ascii=False, indent=2))
