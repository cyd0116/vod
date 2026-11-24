# -*- coding: utf-8 -*-
"""
1905电影网 —— 影视仓(Hipy/T4/drpyS) Python 采集规则
严格对应 Java 版 Web1905 反编译实现
"""
import sys
import re
import json
import time
import uuid
import hashlib
import gzip

sys.path.append('..')
from base.spider import Spider

from urllib import parse as urlparse
from urllib import request as urlrequest
import ssl


class Spider(Spider):

    # ---- 常量（对应 Java 静态字段与各方法内硬编码常量） --------------
    PAT = re.compile(r'play/(.*?).sh')     # 与 sget-object a 一致

    UA = ('Mozilla/5.0 (Linux; Android 17; PKG110 Build/UKQ1.231108.001) '
          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.8059.43 '
          'Mobile Safari/537.36')

    SITE = 'https://www.1905.com'
    API_VIDEOINFO = 'https://profile.m1905.com/mvod/getVideoinfo.php'
    API_SIDEBAR = SITE + '/api/content/?m=Vod&a=getVodSidebar&id='
    API_CATEGORY = SITE + '/m/api/loadpage/vodlist/?o=3&catid='
    API_SEARCH = SITE + '/search/index-p-type-all-q-'

    # 与 Java 里 uuid 后拼接的固定 key 一致
    SIGN_SECRET = 'dde3d61a0411511d'

    # 与 homeContent 中的两组数组一致
    CAT_IDS = ['', '922', '927', '586', '178', '1024']
    CAT_NAMES = ['电影', '微电影', '记录片', '晚会', '独家', '综艺']

    # ------------------------------------------------------ 基础
    def getName(self):
        return '1905电影'

    def init(self, extend=''):
        self._cookie = str(extend or '').strip()
        self._timeout = 15
        self._opener = None

    def isVideoFormat(self, url):
        return any(k in str(url or '').lower()
                   for k in ('.m3u8', '.mp4', '.flv', '.ts?', '.m3u8?'))

    def manualVideoCheck(self):
        return False

    def log(self, msg):
        try:
            super(Spider, self).log(msg)
        except Exception:
            print(msg)

    # ------------------------------------------------------ 请求封装
    # 对应 Java 的 private a(String) 方法：
    #   UA = 移动端 Chrome，Referer = https://www.1905.com/，
    #   Accept = application/json, text/plain, */*
    def _fetch_text(self, url, referer='https://www.1905.com/'):
        headers = {
            'User-Agent': self.UA,
            'Referer': referer,
            'Accept': 'application/json, text/plain, */*',
        }
        if self._cookie:
            headers['Cookie'] = self._cookie

        # 优先框架 fetch（与 Java merge.k.b.l 等价）
        fetch = getattr(self, 'fetch', None)
        if callable(fetch):
            try:
                try:
                    rsp = fetch(url, headers=headers, timeout=self._timeout,
                                verify=False, allow_redirects=True)
                except TypeError:
                    try:
                        rsp = fetch(url, headers=headers)
                    except TypeError:
                        rsp = fetch(url)
                if rsp is None:
                    raise ValueError('empty response')
                if hasattr(rsp, 'text'):
                    return rsp.text or ''
                if hasattr(rsp, 'content'):
                    return self._decode(rsp.content, rsp)
                return str(rsp)
            except Exception as e:
                self.log('[1905] fetch 失败: %s -> %s' % (url, e))

        # urllib 兜底
        if self._opener is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._opener = urlrequest.build_opener(
                urlrequest.HTTPSHandler(context=ctx))
        try:
            req = urlrequest.Request(url, headers=headers)
            with self._opener.open(req, timeout=self._timeout) as resp:
                raw = resp.read()
            return self._decode(raw, None)
        except Exception as e:
            self.log('[1905] urllib 失败: %s -> %s' % (url, e))
        return ''

    def _decode(self, raw, resp):
        if not raw:
            return ''
        if resp is not None and resp.headers.get('Content-Encoding', '') == 'gzip':
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        elif raw[:2] == b'\x1f\x8b':
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        try:
            return raw.decode('utf-8')
        except Exception:
            return raw.decode('gbk', 'ignore')

    # ------------------------------------------------------ vod 构造辅助
    # 对应 Java 的 merge.b.k.b(cid, title, pic, remark, list)
    @staticmethod
    def _add_vod(cid, title, pic, remark, arr):
        cid = str(cid or '').strip()
        title = str(title or '').strip()
        if not cid or not title:
            return
        arr.append({
            'vod_id': cid,
            'vod_name': title,
            'vod_pic': str(pic or ''),
            'vod_remarks': str(remark or ''),
        })

    # ------------------------------------------------------ homeContent
    # 对应 Java homeContent(Z)：仅返回两个数组拼出的分类列表
    def homeContent(self, filter):
        try:
            classes = [{'type_id': cid, 'type_name': name}
                       for cid, name in zip(self.CAT_IDS, self.CAT_NAMES)]
            return {'class': classes}
        except Exception as e:
            self.log('[1905] homeContent 失败: %s' % e)
            return {'class': []}

    # ------------------------------------------------------ categoryContent
    # 对应 Java categoryContent：
    #   GET https://www.1905.com/m/api/loadpage/vodlist/?o=3&catid=<tid>&order=3&page=<pg>
    #   解析 list[].{contentid,title,thumb,score}
    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': int(pg or 1) if str(pg or '').isdigit() else 1,
                  'pagecount': 1, 'limit': 0, 'total': 0}
        try:
            pg = str(pg or '1')
            url = '%s%s&order=3&page=%s' % (self.API_CATEGORY, tid, pg)
            text = self._fetch_text(url)
            if not text:
                return result
            data = json.loads(text)
            videos = []
            for it in (data.get('list') or []):
                if not isinstance(it, dict):
                    continue
                self._add_vod(it.get('contentid', ''), it.get('title', ''),
                              it.get('thumb', ''), it.get('score', ''), videos)
            result.update({
                'list': videos,
                'page': int(pg),
                # Java 版 merge.b.h.a 只传 page、videos，未传总页数，这里与之一致
                'pagecount': 9999,
                'limit': len(videos) or 24,
                'total': 9999 * (len(videos) or 24),
            })
        except Exception as e:
            self.log('[1905] categoryContent 失败: %s' % e)
        return result

    # ------------------------------------------------------ detailContent
    # 对应 Java detailContent：
    #   GET https://www.1905.com/api/content/?m=Vod&a=getVodSidebar&id=<id>&fomat=json
    #   play_url = "title$id" + series_data 中每项 "ser_title$ser_cid"
    #   play_from = "1905"
    def detailContent(self, array):
        try:
            vid = str(array[0]).split('###')[0].strip()
            if not vid:
                return {'list': []}
            url = '%s%s&fomat=json' % (self.API_SIDEBAR, vid)
            text = self._fetch_text(url,
                                    referer='https://www.1905.com/vod/play/%s.shtml' % vid)
            if not text:
                return {'list': []}
            data = json.loads(text)

            title = data.get('title', '')
            thumb = data.get('thumb', '')
            remark = data.get('commendreason', '')
            content = data.get('description', '')
            director = data.get('direct', '')
            actor = data.get('starring', '')

            play_url_list = ['%s$%s' % (title, vid)]
            info = data.get('info') or {}
            for ser in (info.get('series_data') or []):
                if not isinstance(ser, dict):
                    continue
                ser_cid = str(ser.get('contentid', '')).strip()
                if ser_cid:
                    ser_title = ser.get('title', '') or title
                    play_url_list.append('%s$%s' % (ser_title, ser_cid))

            vod = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': thumb,
                'vod_remarks': remark,
                'vod_content': content,
                'vod_director': director,
                'vod_actor': actor,
                'vod_play_from': '1905',
                'vod_play_url': '#'.join(play_url_list),
            }
            return {'list': [vod]}
        except Exception as e:
            self.log('[1905] detailContent 失败: %s' % e)
            return {'list': []}

    # ------------------------------------------------------ searchContent
    # 对应 Java searchContent：
    #   GET https://www.1905.com/search/index-p-type-all-q-<urlencode(key)>.html
    #   选择器：div.movie_box > div > div
    #   a = div > ul > li.paly-tab-icon > a @href（正则截取 contentid）
    #   img = div > div.movie-pic > a > img @alt/@src
    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'page': 1, 'pagecount': 1, 'total': 0}
        try:
            kw = urlparse.quote(str(key))
            url = '%s%s.html' % (self.API_SEARCH, kw)
            html = self._fetch_text(url,
                                    referer='https://www.1905.com/search/')
            if not html:
                return result
            videos = self._parse_search(html)
            result.update({
                'list': videos,
                'page': 1,
                'pagecount': 1,
                'total': len(videos),
            })
        except Exception as e:
            self.log('[1905] searchContent 失败: %s' % e)
        return result

    def _parse_search(self, html):
        videos = []
        try:
            root = self.html(html)
            if root is None:
                return videos
            for div in root.xpath(
                    "//div[contains(@class,'movie_box')]/div/div"):
                try:
                    # a: div > ul > li.paly-tab-icon > a @href
                    a_nodes = div.xpath(
                        ".//ul/li[contains(@class,'paly-tab-icon')]/a")
                    href = ''
                    if a_nodes:
                        hrefs = a_nodes[0].xpath('./@href')
                        href = (hrefs[0] if hrefs else '').strip()
                    if not href:
                        continue

                    m = self.PAT.search(href)
                    vid = m.group(1) if m else href

                    # img: div > div.movie-pic > a > img @alt @src
                    imgs = div.xpath(
                        ".//div[contains(@class,'movie-pic')]/a/img")
                    if not imgs:
                        continue
                    img = imgs[0]
                    alt = (img.xpath('./@alt') or [''])[0].strip()
                    src = (img.xpath('./@src') or [''])[0].strip()
                    if not alt:
                        continue
                    self._add_vod(vid, alt, src, '', videos)
                except Exception:
                    continue
        except Exception as e:
            self.log('[1905] 搜索解析失败: %s' % e)
        return videos

    # ------------------------------------------------------ playerContent
    # 对应 Java playerContent：
    #   nonce   = System.currentTimeMillis()/1000
    #   expire  = nonce + 600
    #   uuid    = UUID.randomUUID()   (保留带 - 的形式用于签名与请求)
    #   playerid= uuid.replace("-","").substring(5,20)
    #   page    = https://www.1905.com/vod/play/<cid>.shtml  (冒号/斜杠 URL 编码)
    #   raw     = "cid=%s&expiretime=%d&nonce=%d&page=%s&playerid=%s&type=hls&uuid=%s.dde3d61a0411511d"
    #   sign    = sha1(raw)
    #   GET profile.m1905.com/mvod/getVideoinfo.php?...&callback=
    #   去掉首尾 "(" ")" 后解析 JSON
    #   优先 uhd -> hd -> sd，拼接 host + sign + path
    def playerContent(self, flag, id, vipFlags):
        try:
            cid = str(id).strip()
            now = int(time.time())
            expire = now + 600
            uid = str(uuid.uuid4())
            playerid = uid.replace('-', '')[5:20]

            page = 'https://www.1905.com/vod/play/%s.shtml' % cid
            page_enc = page.replace(':', '%3A').replace('/', '%2F')

            raw = ('cid=%s&expiretime=%d&nonce=%d&page=%s&playerid=%s'
                   '&type=hls&uuid=%s.%s' % (
                       cid, expire, now, page_enc, playerid,
                       uid, self.SIGN_SECRET))
            sign = hashlib.sha1(raw.encode('utf-8')).hexdigest()

            api = ('%s?nonce=%d&expiretime=%d&cid=%s&uuid=%s&playerid=%s'
                   '&page=%s&type=hls&signature=%s&callback=' % (
                       self.API_VIDEOINFO, now, expire, cid, uid,
                       playerid, page_enc, sign))

            text = self._fetch_text(api,
                                    referer='https://www.1905.com/')
            text = (text or '').replace('(', '').replace(')', '').strip()
            if not text:
                raise ValueError('空响应')
            data = json.loads(text)
            d = data.get('data') or {}

            sign_map = d.get('sign') or {}
            quality_map = d.get('quality') or {}
            path_map = d.get('path') or {}

            keys = list(sign_map.keys())
            q = ''
            if 'uhd' in keys:
                q = 'uhd'
            elif 'hd' in keys:
                q = 'hd'
            elif 'sd' in keys:
                q = 'sd'
            if not q:
                raise ValueError('无可用清晰度 keys=%s' % keys)

            host = ((quality_map.get(q) or {}).get('host') or '')
            path = ((path_map.get(q) or {}).get('path') or '')
            sign_s = (sign_map.get(q) or {}).get('sign') or ''
            if isinstance(sign_s, dict):
                sign_s = sign_s.get('sign', '') or ''
            if not path:
                raise ValueError('path 为空')

            play_url = host + sign_s + path
            return {
                'parse': 0,
                'playUrl': '',
                'url': play_url,
                'header': {
                    'User-Agent': self.UA,
                    'Referer': 'https://www.1905.com/',
                },
            }
        except Exception as e:
            self.log('[1905] playerContent 降级解析: %s' % e)
            return {
                'parse': 1,
                'playUrl': '',
                'url': 'https://www.1905.com/vod/play/%s.shtml' % id,
                'header': {
                    'User-Agent': self.UA,
                    'Referer': 'https://www.1905.com/',
                },
            }

    # ------------------------------------------------------ 本地代理（可选）
    # Java 版没有 localProxy，这里给个最小实现，便于 m3u8/ts 需要代理时使用
    def localProxy(self, param):
        try:
            url = ''
            if isinstance(param, dict):
                url = param.get('url') or param.get('path') or ''
            elif isinstance(param, (list, tuple)) and param:
                url = str(param[0])
            else:
                url = str(param or '')
            if not url.startswith('http'):
                return [404, 'text/plain', 'invalid proxy url', {}]
            req = urlrequest.Request(url, headers={
                'User-Agent': self.UA,
                'Referer': 'https://www.1905.com/',
            })
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urlrequest.urlopen(req, timeout=self._timeout, context=ctx) as resp:
                raw = resp.read()
                ctype = resp.headers.get('Content-Type', 'application/octet-stream')
            if url.split('?')[0].endswith('.ts'):
                ctype = 'video/MP2T'
            return [200, ctype, raw, {}]
        except Exception as e:
            self.log('[1905] localProxy: %s' % e)
            return [500, 'text/plain', '', {}]