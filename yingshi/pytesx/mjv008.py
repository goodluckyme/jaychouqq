# coding=utf-8
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def getName(self):
        return "MJ视频"

    def init(self, extend=""):
        self.home_url = "https://mjv008.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; M2102J2SC Build/UKQ1.240624.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.86 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.home_url + '/zh/',
        })
        # 自动通过年龄确认
        try:
            self.session.get(
                self.home_url + '/zh/chinese_IamOverEighteenYearsOld/19/index.html',
                timeout=10
            )
        except Exception:
            pass

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.flv', 'imgstream'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    classes = [
        {"type_id": "chinese", "type_name": "中文字幕"},
        {"type_id": "censored", "type_name": "有码AV"},
        {"type_id": "uncensored", "type_name": "无码AV"},
        {"type_id": "amateurjav", "type_name": "素人AV"},
        {"type_id": "reducing-mosaic", "type_name": "无码破解"},
        {"type_id": "animation", "type_name": "H动画"},
        {"type_id": "dt", "type_name": "国产自拍"},
        {"type_id": "18H", "type_name": "18H长篇"},
    ]

    # 分类对应的列表路径前缀
    cate_map = {
        "chinese": "/zh/chinese_random/all/",
        "censored": "/zh/censored_random/all/",
        "uncensored": "/zh/uncensored_random/all/",
        "amateurjav": "/zh/amateurjav_random/all/",
        "reducing-mosaic": "/zh/reducing-mosaic_random/all/",
        "animation": "/zh/animation_random/all/",
        "dt": "/zh/dt_random/all/",
        "18H": "/zh/18H_random/all/",
    }

    def homeContent(self, filter):
        return {"class": self.classes, "filters": {}}

    def _parse_list(self, html):
        videos = []
        soup = BeautifulSoup(html, 'html.parser')
        # 匹配内容链接
        for a in soup.select('a[href*="_content/"]'):
            href = a.get('href', '')
            if not re.search(r'_content/\d+/', href):
                continue
            # 去重
            if any(v['vod_id'] == href for v in videos):
                continue
            title = a.get('title') or a.get_text(strip=True) or ''
            if not title or len(title) < 2:
                # 尝试从父级或兄弟节点取标题
                parent = a.find_parent(['div', 'li', 'td'])
                if parent:
                    t = parent.select_one('.archive-title, .title, h3, h4')
                    if t:
                        title = t.get_text(strip=True)
            if not title:
                continue
            # 封面
            pic = ''
            img = a.select_one('img') or (a.find_parent() and a.find_parent().select_one('img'))
            if img:
                pic = img.get('src') or img.get('data-src') or img.get('data-original') or ''
            videos.append({
                "vod_id": href if href.startswith('http') else urljoin(self.home_url, href),
                "vod_name": title[:80],
                "vod_pic": urljoin(self.home_url, pic) if pic else '',
                "vod_remarks": '',
            })
        return videos

    def homeVideoContent(self):
        videos = []
        try:
            # 中文字幕首页
            url = self.home_url + '/zh/chinese_random/all/index.html'
            resp = self.session.get(url, timeout=12)
            resp.encoding = 'utf-8'
            videos = self._parse_list(resp.text)
        except Exception as e:
            print('homeVideoContent error:', e)
        return {'list': videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        page = int(pg) if str(pg).isdigit() else 1
        try:
            prefix = self.cate_map.get(str(tid), '/zh/chinese_random/all/')
            if page <= 1:
                url = self.home_url + prefix + 'index.html'
            else:
                url = self.home_url + prefix + str(page) + '.html'
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            videos = self._parse_list(resp.text)
        except Exception as e:
            print('categoryContent error:', e)
        return {
            'list': videos,
            'page': page,
            'pagecount': 999 if len(videos) >= 12 else page,
            'limit': 30,
            'total': 999999,
        }

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        try:
            vid = ids[0]
            url = vid if vid.startswith('http') else urljoin(self.home_url, vid)
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')

            vod = {
                "vod_id": vid,
                "vod_name": "未知",
                "vod_pic": "",
                "vod_content": "",
                "vod_remarks": "",
            }

            # 标题
            h1 = soup.select_one('h1') or soup.select_one('.archive-title') or soup.select_one('title')
            if h1:
                vod['vod_name'] = h1.get_text(strip=True).replace(' - MJ', '').strip()[:80]

            # 封面
            img = soup.select_one('#player-wrap img') or soup.select_one('.player-wrap img') or soup.select_one('img[src*="imgstream"]')
            if img:
                vod['vod_pic'] = img.get('src') or img.get('data-src') or ''

            # 简介
            desc = soup.select_one('.entry-content p') or soup.select_one('.content p')
            if desc:
                vod['vod_content'] = desc.get_text(strip=True)[:500]

            # 播放地址提取
            play_url = ''
            # 1. 直接匹配 mp4 / m3u8
            m = re.search(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)[^"\'\s<>]*', html)
            if m:
                play_url = m.group(0)
            # 2. 从相关推荐里找与当前番号匹配的
            if not play_url:
                code_m = re.search(r'/([A-Z0-9]+-[0-9]+)\.html', url, re.I)
                if code_m:
                    code = code_m.group(1)
                    m2 = re.search(rf'https?://[^"\'\s<>]*{re.escape(code)}[^"\'\s<>]*\.(?:mp4|m3u8)', html, re.I)
                    if m2:
                        play_url = m2.group(0)

            if play_url:
                vod['vod_play_from'] = 'MJ'
                vod['vod_play_url'] = f'正片${play_url}'
            else:
                # 兜底返回页面，交给解析
                vod['vod_play_from'] = 'MJ'
                vod['vod_play_url'] = f'播放${url}'

            return {'list': [vod]}
        except Exception as e:
            print('detailContent error:', e)
        return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            encoded = quote(key)
            # 站点搜索形式
            url = f"{self.home_url}/zh/search/{encoded}/1.html"
            if str(pg) != "1":
                url = f"{self.home_url}/zh/search/{encoded}/{pg}.html"
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            videos = self._parse_list(resp.text)
            # 如果搜索页结构不同，再尝试另一种
            if not videos:
                url2 = f"{self.home_url}/zh/chinese_random/all/index.html"
                resp2 = self.session.get(url2, timeout=12)
                resp2.encoding = 'utf-8'
                all_v = self._parse_list(resp2.text)
                videos = [v for v in all_v if key.lower() in v['vod_name'].lower()]
            return {'list': videos}
        except Exception as e:
            print('searchContent error:', e)
        return {'list': []}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.session.headers.get('User-Agent', ''),
            'Referer': self.home_url + '/',
        }
        play = str(id or '')
        # 已经是直链
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}

        # 再请求一次页面提取
        try:
            url = play if play.startswith('http') else urljoin(self.home_url, play)
            resp = self.session.get(url, timeout=12)
            resp.encoding = 'utf-8'
            html = resp.text
            m = re.search(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)[^"\'\s<>]*', html)
            if m:
                return {'parse': 0, 'jx': '0', 'url': m.group(0), 'header': header}
        except Exception:
            pass

        return {'parse': 1, 'jx': '1', 'url': play if play.startswith('http') else urljoin(self.home_url, play), 'header': header}

    def localProxy(self, params):
        return None