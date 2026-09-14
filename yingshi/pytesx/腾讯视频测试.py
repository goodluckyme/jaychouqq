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
        self.listApi = 'https://v.qq.com/x/bu/pagesheet/list'
        self.searchApi = 'https://v.qq.com/x/search/'
        self.nodeApi = 'https://node.video.qq.com'
        self.pbApi = 'https://pbaccess.video.qq.com'
        self.userAgent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        
        # 频道映射：tid -> channel 参数
        self.channels = {
            '1': {'name': '电影', 'channel': 'movie'},
            '2': {'name': '电视剧', 'channel': 'tv'},
            '3': {'name': '动漫', 'channel': 'cartoon'},
            '4': {'name': '综艺', 'channel': 'variety'},
            '5': {'name': '纪录片', 'channel': 'doco'},
            '6': {'name': '少儿', 'channel': 'child'},
            '7': {'name': '游戏', 'channel': 'game'},
        }
        
        # 筛选配置（参考腾讯视频页面常见筛选项，部分参数可能随时间变化）
        self.filters = {
            "1": [  # 电影
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
                    {"n": "2010-2019", "v": "2010"},
                    {"n": "更早", "v": "2009"}
                ]},
                {"key": "itype", "name": "类型", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "动作", "v": "1"},
                    {"n": "喜剧", "v": "2"},
                    {"n": "爱情", "v": "3"},
                    {"n": "科幻", "v": "4"},
                    {"n": "恐怖", "v": "5"},
                    {"n": "剧情", "v": "6"},
                    {"n": "战争", "v": "7"},
                    {"n": "悬疑", "v": "8"},
                    {"n": "动画", "v": "9"},
                    {"n": "奇幻", "v": "10"}
                ]},
                {"key": "iarea", "name": "地区", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "内地", "v": "1"},
                    {"n": "香港", "v": "2"},
                    {"n": "台湾", "v": "3"},
                    {"n": "美国", "v": "4"},
                    {"n": "韩国", "v": "5"},
                    {"n": "日本", "v": "6"},
                    {"n": "其他", "v": "7"}
                ]}
            ],
            "2": [  # 电视剧
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
                ]},
                {"key": "itype", "name": "类型", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "国产剧", "v": "1"},
                    {"n": "港剧", "v": "2"},
                    {"n": "韩剧", "v": "3"},
                    {"n": "美剧", "v": "4"},
                    {"n": "日剧", "v": "5"},
                    {"n": "泰剧", "v": "6"},
                    {"n": "其他", "v": "7"}
                ]},
                {"key": "iarea", "name": "地区", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "内地", "v": "1"},
                    {"n": "香港", "v": "2"},
                    {"n": "台湾", "v": "3"},
                    {"n": "韩国", "v": "4"},
                    {"n": "美国", "v": "5"},
                    {"n": "日本", "v": "6"}
                ]}
            ],
            "3": [  # 动漫
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
                ]},
                {"key": "itype", "name": "类型", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "热血", "v": "1"},
                    {"n": "恋爱", "v": "2"},
                    {"n": "科幻", "v": "3"},
                    {"n": "奇幻", "v": "4"},
                    {"n": "搞笑", "v": "5"},
                    {"n": "日常", "v": "6"}
                ]}
            ],
            "4": [  # 综艺
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "更早", "v": "2023"}
                ]}
            ],
            "5": [  # 纪录片
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "6": [  # 少儿
                {"key": "sort", "name": "排序", "value": [
                    {"n": "最热", "v": "75"},
                    {"n": "最新", "v": "18"}
                ]}
            ],
            "7": [  # 游戏
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

    def fetch(self, url, headers=None, params=None, method='GET', data=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=12)
            else:
                if params:
                    response = requests.get(url, headers=headers, params=params, timeout=12)
                else:
                    response = requests.get(url, headers=headers, timeout=12)
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
        result = {}
        videos = []
        try:
            # 取几个热门频道的前几页作为首页推荐
            for tid in ['2', '1', '3', '4']:
                channel = self.channels.get(tid, {}).get('channel', 'tv')
                params = {
                    '_all': '1',
                    'append': '1',
                    'channel': channel,
                    'listpage': '1',
                    'offset': '0',
                    'pagesize': '12',
                    'sort': '75'
                }
                response = self.fetch(self.listApi, params=params)
                if response:
                    items = self._parseListHtml(response.text)
                    videos.extend(items[:6])
                if len(videos) >= 24:
                    break
        except Exception as e:
            print(f"获取首页视频失败: {e}")
        result['list'] = videos
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []
        try:
            channel_info = self.channels.get(str(tid), {})
            channel = channel_info.get('channel', 'tv')
            
            sort = '75'
            if extend and isinstance(extend, dict):
                sort = extend.get('sort', '75') or '75'
            
            offset = (int(pg) - 1) * 30
            params = {
                '_all': '1',
                'append': '1',
                'channel': channel,
                'listpage': '1',
                'offset': str(offset),
                'pagesize': '30',
                'sort': sort
            }
            
            # 附加筛选参数
            if extend and isinstance(extend, dict):
                for k, v in extend.items():
                    if k != 'sort' and v:
                        params[k] = v
            
            response = self.fetch(self.listApi, params=params)
            if response:
                videos = self._parseListHtml(response.text)
                pagecount = int(pg) + 1 if len(videos) >= 20 else int(pg)
                total = len(videos) * int(pg)
            else:
                pagecount = int(pg)
                total = len(videos)
        except Exception as e:
            print(f"获取分类内容失败: {e}")
            pagecount = int(pg)
            total = len(videos)
        
        result['list'] = videos
        result['page'] = int(pg)
        result['pagecount'] = pagecount
        result['limit'] = 30
        result['total'] = total
        return result

    def _parseListHtml(self, html):
        """解析 pagesheet/list 返回的 HTML"""
        videos = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select('.list_item') or soup.select('div.list_item')
            for item in items:
                try:
                    a_tag = item.select_one('a')
                    if not a_tag:
                        continue
                    title = a_tag.get('title') or a_tag.get_text(strip=True)
                    href = a_tag.get('href', '')
                    # 提取 cid 或 vid
                    cid = a_tag.get('data-float') or a_tag.get('data-id') or ''
                    if not cid and href:
                        # 从链接提取，例如 /x/cover/xxxxx.html 或 /x/cover/xxxxx/yyyy.html
                        m = re.search(r'/cover/([a-zA-Z0-9]+)', href)
                        if m:
                            cid = m.group(1)
                        else:
                            m = re.search(r'/page/([a-zA-Z0-9]+)', href)
                            if m:
                                cid = m.group(1)
                    if not cid:
                        continue
                    
                    img = item.select_one('img')
                    pic = ''
                    if img:
                        pic = img.get('src') or img.get('data-src') or img.get('r-lazyload') or ''
                        if pic.startswith('//'):
                            pic = 'https:' + pic
                    
                    remarks = ''
                    caption = item.select_one('.figure_caption') or item.select_one('.figure_info')
                    if caption:
                        remarks = caption.get_text(strip=True)
                    
                    videos.append({
                        "vod_id": cid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remarks
                    })
                except Exception as e:
                    continue
        except Exception as e:
            print(f"解析列表HTML失败: {e}")
        return videos

    def detailContent(self, ids):
        result = {}
        try:
            video_id = ids[0]
            # video_id 可能是 cid，也可能是 cid_vid 形式
            cid = video_id.split('_')[0] if '_' in video_id else video_id
            
            album_name = ''
            album_pic = ''
            album_desc = ''
            directors = []
            actors = []
            episodes = []
            
            # 1. 尝试通过 float_vinfo2 获取基础信息
            info_url = f'{self.nodeApi}/x/api/float_vinfo2'
            params = {'cid': cid}
            response = self.fetch(info_url, params=params)
            if response:
                try:
                    text = response.text
                    # 可能是 JSONP
                    if text.startswith('jQuery') or 'callback' in text.lower():
                        m = re.search(r'\((\{.*\})\)', text, re.DOTALL)
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
                        # 演员导演
                        nam = data.get('nam') or []
                        if nam and isinstance(nam, list) and len(nam) > 0:
                            if isinstance(nam[0], list):
                                actors = [str(x) for x in nam[0] if x]
                            else:
                                actors = [str(x) for x in nam if x]
                except Exception as e:
                    print(f"解析 float_vinfo2 失败: {e}")
            
            # 2. 获取剧集列表（通过页面或接口）
            # 优先尝试 cover 页面解析
            cover_url = f'https://v.qq.com/x/cover/{cid}.html'
            page_resp = self.fetch(cover_url)
            if page_resp:
                try:
                    html = page_resp.text
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 标题
                    if not album_name:
                        title_tag = soup.select_one('h1') or soup.select_one('.video_title') or soup.select_one('[class*="title"]')
                        if title_tag:
                            album_name = title_tag.get_text(strip=True)
                    
                    # 简介
                    if not album_desc:
                        desc_tag = soup.select_one('.video_desc') or soup.select_one('[class*="desc"]') or soup.select_one('.summary')
                        if desc_tag:
                            album_desc = desc_tag.get_text(strip=True)
                    
                    # 封面
                    if not album_pic:
                        img_tag = soup.select_one('.figure img') or soup.select_one('img[src*="puui"]')
                        if img_tag:
                            album_pic = img_tag.get('src') or img_tag.get('data-src') or ''
                            if album_pic.startswith('//'):
                                album_pic = 'https:' + album_pic
                    
                    # 尝试从页面脚本中提取剧集信息
                    scripts = soup.find_all('script')
                    for script in scripts:
                        txt = script.string or ''
                        if 'video_ids' in txt or 'episode' in txt.lower() or 'cid' in txt:
                            # 简单提取 vid 列表
                            vids = re.findall(r'"vid"\s*:\s*"([a-zA-Z0-9]+)"', txt)
                            titles = re.findall(r'"title"\s*:\s*"([^"]+)"', txt)
                            if vids:
                                for i, vid in enumerate(vids[:100]):  # 限制数量
                                    ep_name = titles[i] if i < len(titles) else f'第{i+1}集'
                                    play_url = f'https://v.qq.com/x/cover/{cid}/{vid}.html'
                                    episodes.append({
                                        'name': ep_name,
                                        'url': play_url
                                    })
                                break
                    
                    # 如果脚本没拿到，尝试播放列表 DOM
                    if not episodes:
                        play_items = soup.select('.mod_episode a') or soup.select('[class*="episode"] a') or soup.select('.play-list a')
                        for a in play_items:
                            ep_name = a.get('title') or a.get_text(strip=True)
                            href = a.get('href', '')
                            if href and ep_name:
                                if not href.startswith('http'):
                                    href = urllib.parse.urljoin(self.siteUrl, href)
                                episodes.append({
                                    'name': ep_name,
                                    'url': href
                                })
                except Exception as e:
                    print(f"解析封面页失败: {e}")
            
            # 如果仍然没有剧集，至少放一个入口
            if not episodes:
                episodes = [{
                    'name': album_name or '正片',
                    'url': f'https://v.qq.com/x/cover/{cid}.html'
                }]
            
            # 构建播放列表
            play_from = ['腾讯视频']
            play_urls = []
            for ep in episodes:
                ep_name = ep.get('name', '')
                ep_url = ep.get('url', '')
                if ep_url:
                    play_urls.append(f"{ep_name}${ep_url}")
            
            play_url = '#'.join(play_urls)
            
            album_desc = (album_desc or '').replace('\n\n', '\n').strip()
            
            vod = {
                "vod_id": video_id,
                "vod_name": album_name or cid,
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
        videos = []
        try:
            # 使用搜索页面
            params = {
                'q': key,
                'pageNum': str(pg)
            }
            response = self.fetch(self.searchApi, params=params)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 常见搜索结果选择器
                items = soup.select('.result_item') or soup.select('.list_item') or soup.select('[class*="result"]')
                for item in items:
                    try:
                        a_tag = item.select_one('a')
                        if not a_tag:
                            continue
                        title = a_tag.get('title') or a_tag.get_text(strip=True)
                        href = a_tag.get('href', '')
                        cid = ''
                        m = re.search(r'/cover/([a-zA-Z0-9]+)', href)
                        if m:
                            cid = m.group(1)
                        else:
                            m = re.search(r'/page/([a-zA-Z0-9]+)', href)
                            if m:
                                cid = m.group(1)
                        if not cid or not title:
                            continue
                        
                        img = item.select_one('img')
                        pic = ''
                        if img:
                            pic = img.get('src') or img.get('data-src') or ''
                            if pic.startswith('//'):
                                pic = 'https:' + pic
                        
                        remarks = ''
                        info = item.select_one('.figure_info') or item.select_one('.result_info')
                        if info:
                            remarks = info.get_text(strip=True)[:30]
                        
                        videos.append({
                            "vod_id": cid,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remarks
                        })
                    except Exception:
                        continue
                
                result = {
                    'list': videos,
                    'page': int(pg),
                    'pagecount': 999,
                    'limit': 20,
                    'total': len(videos)
                }
        except Exception as e:
            print(f"搜索失败: {e}")
        if not result:
            result = {'list': videos, 'page': int(pg), 'pagecount': int(pg), 'limit': 20, 'total': len(videos)}
        return result

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            play_url = id
            # 统一转为 https 和标准域名
            if play_url and play_url.startswith('http'):
                play_url = play_url.replace('http://', 'https://')
                play_url = play_url.replace('https://www.v.qq.com/', 'https://v.qq.com/')
            
            if self.isVideoFormat(play_url):
                result["parse"] = 0
                result["url"] = play_url
            else:
                # 腾讯视频链接一般需要解析（jx）
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

    def _parseVideoItem(self, item):
        """兼容旧结构（如果后续有 JSON 接口可复用）"""
        return {
            "vod_id": str(item.get('cid') or item.get('id') or ''),
            "vod_name": item.get('title') or item.get('name', ''),
            "vod_pic": item.get('pic') or item.get('img', ''),
            "vod_remarks": item.get('remark') or item.get('focus', '')
        }

if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
