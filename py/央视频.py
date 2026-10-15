#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import time
from urllib import request, parse
import urllib

class Spider(Spider):
    def getName(self):
        return "央视频"

    def init(self, extend=""):
        print("============央视频 init============")
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    # ---------- 首页分类 ----------
    def homeContent(self, filter):
        result = {}
        cateManual = {
            "精选点播": "hot",
            "电视剧": "电视剧",
            "纪录片": "纪录片",
            "动画片": "动画片",
            "新闻现场": "新闻",
            "综艺": "综艺",
            "特别节目": "特别节目"
        }
        classes = []
        for k, v in cateManual.items():
            classes.append({
                'type_name': k,
                'type_id': v
            })
        result['class'] = classes
        if filter:
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        return {'list': []}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []
        page = pg if pg else 1

        # 央视频网页端搜索/聚合，用 CNTV 接口兜底
        if tid in ["电视剧", "纪录片", "动画片", "特别节目"]:
            channel_map = {
                "动画片": "CHAL1460955899450127",
                "纪录片": "CHAL1460955924871139",
                "电视剧": "CHAL1460955853485115",
                "特别节目": "CHAL1460955953877151"
            }
            cid = channel_map.get(tid, "")
            url = (
                "https://api.cntv.cn/list/getVideoAlbumList?"
                "channelid={cid}&p={p}&n=24&serviceId=tvcctv&topv=1&t=json"
            ).format(cid=cid, p=page)
            try:
                html = self.webReadFile(url)
                jo = json.loads(html)
                data = jo.get("data", {})
                lst = data.get("list", [])
                for vod in lst:
                    guid = vod.get("id", "")
                    title = vod.get("title", "")
                    img = vod.get("image", "")
                    if not guid:
                        continue
                    videos.append({
                        "vod_id": "vod###%s###%s###%s" % (title, img, guid),
                        "vod_name": title,
                        "vod_pic": img,
                        "vod_remarks": ""
                    })
            except Exception as e:
                print("category err:", e)

        elif tid == "新闻现场":
            # 新闻用栏目接口示例（东方时空/新闻联播可换 column id）
            column_id = "TOPC1451354597100320"
            url = (
                "https://api.cntv.cn/NewVideo/getVideoListByColumn?"
                "id=%s&p=%s&n=30&sort=desc&mode=0&serviceId=tvcctv&t=json"
            ) % (column_id, page)
            videos = self._parse_video_list(url)

        else:
            # hot / 综艺 用搜索兜底
            url = (
                "https://api.cntv.cn/list/getVideoAlbumList?"
                "fc=%s&p=%s&n=24&serviceId=tvcctv&topv=1&t=json"
            ) % (parse.quote(tid), page)
            try:
                jo = json.loads(self.webReadFile(url))
                for vod in jo.get("data", {}).get("list", []):
                    guid = vod.get("id", "")
                    if not guid:
                        continue
                    videos.append({
                        "vod_id": "vod###%s###%s###%s" % (vod.get("title",""), vod.get("image",""), guid),
                        "vod_name": vod.get("title", ""),
                        "vod_pic": vod.get("image", ""),
                        "vod_remarks": ""
                    })
            except Exception as e:
                print(e)

        result['list'] = videos
        result['page'] = int(page)
        result['pagecount'] = 9999 if len(videos) >= 24 else int(page)
        result['limit'] = 90
        result['total'] = 999999
        return result

    # ---------- 详情 ----------
    def detailContent(self, array):
        aid = array[0].split("###")
        title = aid[1]
        img = aid[2]
        guid = aid[3]

        url = "https://api.cntv.cn/NewVideo/getVideoListByAlbumIdNew?id=%s&p=1&n=100&mode=0&serviceId=tvcctv&t=json" % guid
        videoList = []
        try:
            jo = json.loads(self.webReadFile(url))
            for v in jo.get("data", {}).get("list", []):
                g = v.get("guid", "")
                t = v.get("title", "")
                if g:
                    videoList.append("%s$%s" % (t, g))
        except Exception as e:
            print("detail err:", e)

        if not videoList:
            # 单集直连
            videoList.append("%s$%s" % (title, guid))

        vod = {
            "vod_id": array[0],
            "vod_name": title,
            "vod_pic": img,
            "type_name": "央视频",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "央视频点播（CNTV 流）"
        }
        vod['vod_play_from'] = "央视频"
        vod['vod_play_url'] = "#".join(videoList)

        return {'list': [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick):
        key = parse.quote(key)
        url = "https://search.cctv.com/ifsearch.php?page=1&qtext=%s&sort=relevance&pageSize=20&type=video" % key
        videos = []
        try:
            jo = json.loads(self.webReadFile(url))
            for v in jo.get("list", []):
                guid = v.get("id", "")
                title = self.removeHtml(v.get("title", ""))
                img = v.get("imglink", "")
                if not guid:
                    continue
                videos.append({
                    "vod_id": "vod###%s###%s###%s" % (title, img, guid),
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": v.get("uploadtime", "")
                })
        except Exception as e:
            print("search err:", e)
        return {'list': videos}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        result = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
            "Referer": "https://www.yangshipin.cn/"
        }

        # id 可能是 guid，也可能是直链
        if id.startswith("http"):
            result["parse"] = 1
            result["url"] = id
            result["header"] = headers
            return result

        try:
            url = "https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=%s" % id
            jo = json.loads(self.webReadFile(url))
            m3u8 = jo.get("hls_url", "").strip()
            if m3u8:
                # 尝试提高清子流
                m3u8 = self.pick_best_m3u8(m3u8, headers)
                result["parse"] = 0
                result["url"] = m3u8
            else:
                raise Exception("no hls")
        except Exception as e:
            print("player err:", e)
            result["parse"] = 1
            result["url"] = id

        result["playUrl"] = ""
        result["header"] = headers
        return result

    # ------------------------------------------------
    # 工具函数
    # ------------------------------------------------
    def webReadFile(self, urlStr):
        req = urllib.request.Request(url=urlStr, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _parse_video_list(self, url):
        videos = []
        try:
            jo = json.loads(self.webReadFile(url))
            for v in jo.get("data", {}).get("list", []):
                guid = v.get("guid", "")
                if not guid:
                    continue
                videos.append({
                    "vod_id": "vod###%s###%s###%s" % (v.get("title",""), v.get("image",""), guid),
                    "vod_name": v.get("title", ""),
                    "vod_pic": v.get("image", ""),
                    "vod_remarks": ""
                })
        except Exception as e:
            print(e)
        return videos

    def pick_best_m3u8(self, m3u8_url, headers):
        try:
            txt = self.webReadFile(m3u8_url)
            lines = [l.strip() for l in txt.split("\n") if l.strip() and not l.startswith("#")]
            if not lines:
                return m3u8_url
            # 默认取最后一个子流
            last = lines[-1]
            if last.startswith("http"):
                return last
            # 相对路径拼前缀
            base = re.match(r"(https?://[^/]+/[^/]+/)", m3u8_url)
            if base:
                return base.group(1).rstrip("/") + "/" + last
        except Exception:
            pass
        return m3u8_url

    def removeHtml(self, txt):
        if not txt:
            return ""
        txt = re.sub(r"<[^>]+>", "", txt)
        return txt.replace("&nbsp;", " ").strip()

    config = {
        "player": {},
        "filter": {}
    }

    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36",
        "Referer": "https://www.yangshipin.cn/"
    }