#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import urllib.parse
import requests
import json
import time
import re
import sys

sys.path.append('../../')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass

class Spider(Spider):
    def __init__(self):
        self.siteUrl = 'https://v.qq.com'
        # 旧 pagesheet 已 404，保留字段兼容
        self.listApi = 'https://v.qq.com/x/bu/pagesheet/list'
        self.searchApi = 'https://pbaccess.video.qq.com/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch'
        self.nodeApi = 'https://node.video.qq.com'
        self.pbApi = 'https://pbaccess.video.qq.com'
        self.episodeApi = 'https://pbaccess.video.qq.com/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
        self.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        self.channels = {
            '1': {'name': '电影', 'channel': 'movie', 'keyword': '电影'},
            '2': {'name': '电视剧', 'channel': 'tv', 'keyword': '电视剧'},
            '3': {'name': '动漫', 'channel': 'cartoon', 'keyword': '动漫'},
            '4': {'name': '综艺', 'channel': 'variety', 'keyword': '综艺'},
            '5': {'name': '纪录片', 'channel': 'doco', 'keyword': '纪录片'},
            '6': {'name': '少儿', 'channel': 'child', 'keyword': '少儿'},
            '7': {'name': '游戏', 'channel': 'game', 'keyword': '游戏'},
        }
        
        self.filters = {
            "1": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"},
                    {"n": "好评", "v": "21"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "2022", "v": "2022"},
                    {"n": "2021", "v": "2021"},
                    {"n": "2020", "v": "2020"},
                    {"n": "更早", "v": "2019"}
                ]}
            ],
            "2": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "更早", "v": "2022"}
                ]}
            ],
            "3": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "4": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "5": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "6": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "7": [
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ]
        }

    def getName(self):
        return "腾讯视频"

    def init(self, extend=""):
        pass

    def _headers(self, json_mode=False):
        h = {
            'User-Agent': self.userAgent,
            'Referer': 'https://v.qq.com/',
            'Origin': 'https://v.qq.com',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        if json_mode:
            h['Content-Type'] = 'application/json'
            h['Accept'] = 'application/json'
        return h

    def fetch(self, url, headers=None, params=None, method='GET', data=None, json_data=None):
        if headers is None:
            headers = self._headers(json_mode=(json_data is not None))
        try:
            if method.upper() == 'POST':
                if json_data is not None:
                    response = requests.post(url, headers=headers, params=params, json=json_data, timeout=12)
                else:
                    response = requests.post(url, headers=headers, params=params, data=data, timeout=12)
            else:
                response = requests.get(url, headers=headers, params=params, timeout=12)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response
        except Exception as e:
            print(f"请求失败: {url}, 错误: {e}")
            return None

    def homeContent(self, filter):
        result = {}
        classes = []
        for k, v in self.channels.items():
            classes.append({
                'type_id': k,
                'type_name': v['name']
            })
        result['class'] = classes
        if filter:
            result['filters'] = self.filters
        return result

    def homeVideoContent(self):
        """首页推荐：用搜索热门词近似获取"""
        result = {}
        videos = []
        try:
            for kw in ['热播电视剧', '热门电影', '热门动漫', '热门综艺']:
                items = self._search_api(kw, page=0, pagesize=8)
                videos.extend(items[:6])
                if len(videos) >= 24:
                    break
        except Exception as e:
            print(f"获取首页视频失败: {e}")
        result['list'] = videos[:24]
        return result

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类列表：旧 pagesheet 接口已 404。
        当前用「频道关键词 + 搜索接口」做近似分页列表，保证能出内容。
        """
        result = {}
        videos = []
        try:
            channel_info = self.channels.get(str(tid), {})
            keyword = channel_info.get('keyword') or channel_info.get('name') or '电影'
            page = max(int(pg) - 1, 0)
            videos = self._search_api(keyword, page=page, pagesize=30)
            pagecount = int(pg) + 1 if len(videos) >= 15 else int(pg)
            total = len(videos) * int(pg) if videos else 0
        except Exception as e:
            print(f"获取分类内容失败: {e}")
            pagecount = int(pg)
            total = 0
        
        result['list'] = videos
        result['page'] = int(pg)
        result['pagecount'] = pagecount
        result['limit'] = 30
        result['total'] = total
        return result

    def _search_api(self, key, page=0, pagesize=20):
        """腾讯视频正式搜索 JSON 接口"""
        videos = []
        params = {'vversion_platform': '2'}
        payload = {
            'version': '25020601',
            'clientType': 1,
            'filterValue': '',
            'uuid': '',
            'query': key,
            'retry': 0,
            'pagenum': int(page),
            'isPrefetch': False,
            'pagesize': int(pagesize),
            'queryFrom': 0,
            'searchDatakey': '',
            'searchFilterValue': '',
        }
        response = self.fetch(self.searchApi, params=params, method='POST', json_data=payload)
        if not response:
            return videos
        try:
            data = response.json()
            items = (data.get('data') or {}).get('normalList', {}).get('itemList') or []
            for it in items:
                doc = it.get('doc') or {}
                vi = it.get('videoInfo') or {}
                vid = doc.get('id') or ''
                title = (vi.get('title') or '').replace('<em>', '').replace('</em>', '').strip()
                if not vid or not title:
                    continue
                pic = vi.get('imgUrl') or ''
                year = str(vi.get('year') or '')
                type_name = vi.get('typeName') or ''
                remarks = f"{type_name} {year}".strip()
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        except Exception as e:
            print(f"解析搜索结果失败: {e}")
        return videos

    def detailContent(self, ids):
        result = {}
        try:
            video_id = ids[0]
            cid = video_id.split('_')[0] if '_' in video_id else video_id
            
            album_name = ''
            album_pic = ''
            album_desc = ''
            directors = []
            actors = []
            episodes = []
            
            # 1. float_vinfo2 基础信息
            info_url = f'{self.nodeApi}/x/api/float_vinfo2'
            response = self.fetch(info_url, params={'cid': cid})
            if response:
                try:
                    text = response.text.strip()
                    if text.startswith('jQuery') or '(' in text[:20]:
                        m = re.search(r'\((\{.*\})\)\s*;?\s*$', text, re.DOTALL)
                        if m:
                            text = m.group(1)
                    data = json.loads(text)
                    c = data.get('c') or data.get('data') or {}
                    if isinstance(c, dict):
                        album_name = c.get('title') or c.get('name') or album_name
                        album_desc = c.get('description') or c.get('desc') or album_desc
                        album_pic = c.get('pic') or c.get('img') or album_pic
                        if album_pic and album_pic.startswith('//'):
                            album_pic = 'https:' + album_pic
                    nam = data.get('nam') or []
                    if nam and isinstance(nam, list):
                        if nam and isinstance(nam[0], list):
                            actors = [str(x) for x in nam[0] if x]
                        else:
                            actors = [str(x) for x in nam if x]
                except Exception as e:
                    print(f"解析 float_vinfo2 失败: {e}")
            
            # 2. 剧集列表（GetPageData）
            try:
                ep_url = self.episodeApi + '?video_appid=3000010&vplatform=2'
                payload = {
                    "page_params": {
                        "req_from": "web",
                        "page_type": "detail_operation",
                        "page_id": "vsite_episode_list",
                        "id_type": "1",
                        "cid": cid,
                        "page_num": "",
                        "page_size": "100",
                        "page_context": ""
                    },
                    "has_cache": 1
                }
                ep_resp = self.fetch(ep_url, method='POST', json_data=payload)
                if ep_resp:
                    ep_data = ep_resp.json()
                    module_list = (ep_data.get('data') or {}).get('module_list_datas') or []
                    for mod in module_list:
                        for md in (mod.get('module_datas') or []):
                            item_datas = (md.get('item_data_lists') or {}).get('item_datas') or []
                            for item in item_datas:
                                params = item.get('item_params') or {}
                                title = params.get('union_title') or params.get('title') or ''
                                vid = params.get('vid') or ''
                                if vid:
                                    play_url = f'https://v.qq.com/x/cover/{cid}/{vid}.html'
                                    episodes.append({'name': title or vid, 'url': play_url})
                            if episodes:
                                break
                        if episodes:
                            break
            except Exception as e:
                print(f"获取剧集列表失败: {e}")
            
            if not episodes:
                episodes = [{
                    'name': album_name or '正片',
                    'url': f'https://v.qq.com/x/cover/{cid}.html'
                }]
            
            if not album_name:
                album_name = cid
            
            play_from = ['腾讯视频']
            play_urls = [f"{ep['name']}${ep['url']}" for ep in episodes if ep.get('url')]
            play_url = '#'.join(play_urls)
            album_desc = (album_desc or '').replace('\n\n', '\n').strip()
            
            vod = {
                "vod_id": video_id,
                "vod_name": album_name,
                "vod_pic": album_pic,
                "vod_remarks": f"共{len(episodes)}集" if len(episodes) > 1 else "电影",
                "vod_actor": ' '.join(actors[:10]),
                "vod_director": ' '.join(directors[:5]),
                "vod_content": album_desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join([play_url])
            }
            result['list'] = [vod]
        except Exception as e:
            print(f"获取详情失败: {e}")
            result['list'] = []
        return result

    def searchContent(self, key, quick, pg=1):
        result = {}
        try:
            page = max(int(pg) - 1, 0)
            videos = self._search_api(key, page=page, pagesize=25)
            result = {
                'list': videos,
                'page': int(pg),
                'pagecount': 999 if len(videos) >= 15 else int(pg),
                'limit': 25,
                'total': len(videos)
            }
        except Exception as e:
            print(f"搜索失败: {e}")
            result = {'list': [], 'page': int(pg), 'pagecount': int(pg), 'limit': 25, 'total': 0}
        return result

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        """与爱奇艺一致：非直链走解析站（parse=1 + jx=1）"""
        result = {}
        try:
            play_url = id
            # 统一为 https 标准域名，提升解析站 / OK影视 兼容性
            if play_url and play_url.startswith('http'):
                play_url = play_url.replace('http://', 'https://')
                play_url = play_url.replace('https://www.v.qq.com/', 'https://v.qq.com/')
                play_url = play_url.replace('https://m.v.qq.com/', 'https://v.qq.com/')
            
            if self.isVideoFormat(play_url):
                result["parse"] = 0
                result["url"] = play_url
            else:
                # 与爱奇艺相同策略：交给解析站
                result["parse"] = 1
                result["url"] = play_url
                result["jx"] = "1"
            
            result["header"] = {
                "User-Agent": self.userAgent,
                "Referer": "https://v.qq.com/",
                "Origin": "https://v.qq.com"
            }
        except Exception as e:
            print(f"获取播放内容失败: {e}")
        return result

    def isVideoFormat(self, url):
        video_formats = ['.mp4', '.m3u8', '.ts', '.mkv', '.avi', '.flv', '.webm']
        if url and url.startswith('http'):
            for fmt in video_formats:
                if url.lower().find(fmt) > -1:
                    return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
