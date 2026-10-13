# OK影视专用爬虫插件 | 站点：m.360ba.co（360吧 / 体育直播）
# 说明：目标站点为 uni-app SPA，直播赛事由 https://m.360ba.co/api/web 下的接口提供。
#       - 直播列表：/api/web/live_lists/{class_id}   class_id: 1全部 / 2足球 / 3篮球 / 99综合
#       - 首页热门：/api/web/h5_index                data.hot_matches
#       - 搜索：    /api/web/search 不返回赛事（仅主播），故在本地对全部直播做队名/联赛过滤
#       每条赛事带 url(FLV拉流)/stream/screen_url_m3u8(HLS直播流)；本插件直接嗅探播放，无二级。
# 模板改造点：把原"短视频 /api/video/list"改为"直播 /api/web/live_lists"，播放地址取直播拉流并补 Origin 头。
import sys
import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
requests.packages.urllib3.disable_warnings()

# 核心：继承 OK影视 内置 base.spider.Spider 类（必须保留）
from base.spider import Spider


class Spider(Spider):
    # 编解码分隔符（控制字符，不会出现在标题/URL 中），用于在 vod_id 中携带播放所需字段
    SEP = chr(2)

    # ========== 插件基础配置 ==========
    def getName(self):
        """插件名称：OK影视 插件列表中显示的名称"""
        return "360吧直播"

    # ========== 初始化全局配置 ==========
    def init(self, extend=""):
        super().init(extend)

        # 1. 目标站点（必填）
        self.site_url = "https://m.360ba.co"
        # 2. Web 接口根（直播走 /api/web 下）
        self.api = self.site_url + "/api/web"
        self.live_list_url = self.api + "/live_lists"
        self.h5_index_url = self.api + "/h5_index"
        self.search_url = self.api + "/search"

        # 3. 请求头（移动端 UA；直播拉流域名需校验 Referer + Origin，二者都要带）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            "Referer": self.site_url,
            "Origin": self.site_url,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        }

        # 4. 会话 + 重试（站点偶发抖动，自动重试）
        self.sess = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.sess.mount("https://", HTTPAdapter(max_retries=retry))
        self.sess.mount("http://", HTTPAdapter(max_retries=retry))

        # 5. 分类：1全部 / 2足球 / 3篮球 / 99综合（与 live_lists 的 class_id 对应）
        self.categories = [
            {"type_name": "全部", "type_id": "1"},
            {"type_name": "足球", "type_id": "2"},
            {"type_name": "篮球", "type_id": "3"},
            {"type_name": "综合", "type_id": "99"},
        ]

    # ========== 通用请求：GET 并返回 JSON ==========
    def fetch_json(self, url, params=None, timeout=10):
        try:
            res = self.sess.get(url, headers=self.headers, params=params,
                                timeout=timeout, verify=False)
            if res.ok:
                return res.json()
        except Exception:
            return None
        return None

    # ========== 编码/解码 vod_id ==========
    def _encode(self, url, title, pic, content="", anchor=""):
        return self.SEP.join([url or "", title or "", pic or "", content or "", anchor or ""])

    def _decode(self, vod_id):
        parts = vod_id.split(self.SEP)
        return {
            "url": parts[0] if len(parts) > 0 else "",
            "title": parts[1] if len(parts) > 1 else "",
            "pic": parts[2] if len(parts) > 2 else "",
            "content": parts[3] if len(parts) > 3 else "",
            "anchor": parts[4] if len(parts) > 4 else "",
        }

    # ========== 由赛事字段拼出展示名称（对齐 JS 版 getVideos 逻辑）==========
    def _match_name(self, item):
        league = item.get("league_name_zh") or ""
        home = item.get("home_team_zh") or ""
        away = item.get("away_team_zh") or ""
        name = (league + " " + home + " VS " + away).strip()
        # 名称为空 / 含 undefined / 含 http 时，退回其它可用名称字段
        if (not name) or ("undefined" in name) or ("http" in name):
            name = (item.get("match_title") or item.get("title")
                    or item.get("name") or item.get("nickname") or "体育赛事")
        return name.strip()

    # ========== 取直播播放地址：优先 HLS(m3u8) 兼容性最好，回退 FLV 拉流 ==========
    def _play_url(self, item):
        return (item.get("stream") or item.get("screen_url_m3u8")
                or item.get("url") or "")

    # ========== 赛事状态映射 ==========
    def _state_text(self, s):
        m = {0: "未开始", 1: "直播中", 2: "已结束", 3: "集锦"}
        try:
            return m.get(int(s), "状态%s" % s)
        except Exception:
            return ""

    # ========== 拼装详情简介（联赛/对阵/状态/比分/开赛/观看/主播）==========
    def _build_content(self, item):
        league = item.get("league_name_zh") or ""
        home = item.get("home_team_zh") or ""
        away = item.get("away_team_zh") or ""
        segs = []
        if league:
            segs.append("联赛：" + league)
        if home or away:
            segs.append("对阵：%s VS %s" % (home, away))
        st = self._state_text(item.get("state"))
        if st:
            segs.append("状态：" + st)
        hs, aw = item.get("home_score"), item.get("away_score")
        if hs is not None and aw is not None:
            segs.append("比分：%s-%s" % (hs, aw))
        start = item.get("start_time")
        if start:
            segs.append("开赛：" + str(start))
        viewer = item.get("viewer")
        if viewer not in (None, ""):
            segs.append("观看：%s" % viewer)
        nick = item.get("nickname") or ""
        if nick:
            segs.append("主播：" + nick)
        mt = item.get("match_title")
        if mt:
            segs.append("简介：" + str(mt))
        return "；".join(segs)

    # ========== 构造直播卡片 ==========
    def _build_card(self, item):
        url = self._play_url(item)
        if not url:
            return None
        title = self._match_name(item)
        pic = item.get("cover") or ""
        anchor = item.get("nickname") or ""
        content = self._build_content(item)
        vod_id = self._encode(url, title, pic, content, anchor)
        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": anchor or (item.get("league_name_zh") or ""),
            "vod_content": content,
            "vod_actor": anchor,
            "vod_play_from": "直播源",
            # OK影视 播放地址格式：节点名$地址，多个用 # 分隔
            "vod_play_url": "在线播放$" + url
        }

    # ========== 首页：分类 + 热门赛事 ==========
    def homeContent(self, filter):
        result = {"class": self.categories}
        # 首页热门（h5_index 的 hot_matches），失败不影响分类导航
        hj = self.fetch_json(self.h5_index_url)
        if hj and isinstance(hj.get("data"), dict):
            hot = hj["data"].get("hot_matches") or []
            cards = []
            for it in hot:
                card = self._build_card(it)
                if card:
                    cards.append(card)
            if cards:
                result["list"] = cards
        return result

    # ========== 分类列表接口（直播列表，服务端无翻页，仅第一页）==========
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        data = self.fetch_json(self.live_list_url + "/" + str(tid))
        win = []
        if data and data.get("code") == 200 and isinstance(data.get("data"), dict):
            win = data["data"].get("data", []) or []
        # 容错：个别分类若返回结构不同，尝试直接取列表
        if not isinstance(win, list):
            win = []

        video_list = []
        for it in win:
            card = self._build_card(it)
            if card:
                video_list.append(card)

        total = len(video_list)
        return {
            "list": video_list,
            "page": 1,
            "pagecount": 1,
            "limit": 20,
            "total": total
        }

    # ========== 视频详情接口（直播无二级，直接还原播放地址与简介）==========
    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        dec = self._decode(vod_id)
        if not dec.get("url"):
            return {"list": [{"vod_name": "视频ID格式错误"}]}

        url = dec["url"]
        title = dec["title"]
        pic = dec["pic"]
        content = dec["content"]
        anchor = dec["anchor"]
        detail = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": anchor,
            "vod_remarks": "直播",
            "type_name": "体育直播",
            "vod_play_from": "直播源",
            "vod_play_url": "在线播放$" + url
        }
        return {"list": [detail]}

    # ========== 搜索接口 ==========
    # 说明：站点 /api/web/search 仅返回主播、不返回赛事，故在本地拉取“全部”直播列表，
    #       按队名/联赛关键词过滤，做到“搜索可用”。
    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        k = (key or "").lower().strip()
        if not k:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

        # 本地拉“全部”直播列表做关键词过滤
        data = self.fetch_json(self.live_list_url + "/1")
        win = []
        if data and data.get("code") == 200 and isinstance(data.get("data"), dict):
            win = data["data"].get("data", []) or []
        matched = [x for x in win if k and k in (self._match_name(x).lower())]

        video_list = []
        for it in matched:
            card = self._build_card(it)
            if card:
                video_list.append(card)

        total = len(video_list)
        return {
            "list": video_list,
            "page": 1,
            "pagecount": 1,
            "limit": 20,
            "total": total
        }

    # ========== 播放解析接口 ==========
    def playerContent(self, flag, id, vipFlags):
        # id 形如 "在线播放$https://xxx.flv|.m3u8"，取 $ 后的真实地址
        play_url = id.split("$")[1] if "$" in id else id
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}
        # 直播直链，无需二次解析；带上 Referer + Origin 才能通过拉流域名校验
        return {
            "parse": 0,
            "url": play_url,
            "header": self.headers
        }
