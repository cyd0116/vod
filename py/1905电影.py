# -*- coding: utf-8 -*-
"""
1905电影网 —— FongMi TV Python 源 v3（回归老架构）
==================================================

v3 (2026-11-07) —— 修正 v2 的路线错误:
[R1] 回归老源数据架构。实测对照: 老源（抓 www.1905.com HTML）当前完全可用
    —— 15 个分类、单页 25 条、pagecount≈99、详情/播放全通。
    v2 曾因本机测试时段遇到网宿挑战(403 "Verifying browser environment")
    而整体放弃 www 站退到 m 站首页板块（仅 17 部），属于把环境性/时段性
    拦截当成站点死亡，错误推翻了可用架构。本版恢复老源全部数据面，
    解析正则与老源逐字一致（_extract_list / _page_count / 详情字段）。
[W1] 挑战防御: www 页面 403（含 _jsc_ch_conf 网宿 JS 挑战）时退避重试一次；
    仍被挑战则 homeVideoContent 自动降级为 m.1905.com 板块数据（保证首页
    有内容），category/detail 等入口抛可诊断错误，不伪装空列表（§1.6）。
[S1] 规范对齐（《FongMi写源指南_Python篇》）:
    - 网络 self.net（buffer=3 取 bytes 自行 UTF-8 解码）
    - ext 按 JSON 字符串解析（§1.1）；init() 重置全部实例状态（§2.1）
    - homeContent 只回 class+filters；首页卡片走 homeVideoContent
    - detailContent 收列表；播放值用稳定 vid，playerContent 才解析（§1.3）
    - playerContent: parse/url/header(json.dumps)/format —— HLS 逐字
      application/x-mpegURL（§2.6.2）
    - localProxy -> proxy(params)、getProxyUrl -> proxyUrl（§2.9），
      代理返回 [status, mime, body, headers] 四元组（§2.9.2）
    - 解析失败 parse:1 兜底 www 播放页（§2.6.1/§2.14⑤）
    - 播放地址短 TTL 不持久化（§1.7）；destroy() 清理（§2.13）
[V1] VIP 片: 播放 API 对 VIP 片 StatusCode=404 -> playerContent parse:1
    兜底到 www 播放页（WebView 内可通过挑战）。
[P1] m3u8 代理: 主清单自动跟进最高码率变体 + 相对 URI 改写为绝对地址。
"""

import hashlib
import html as _html
import json
import re
import threading
import time
import uuid as _uuid
from urllib.parse import quote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # ---- 站点常量 ----
    PC_HOST = "https://www.1905.com"
    M_HOST = "https://m.1905.com"
    API_HOST = "https://profile.m1905.com"
    APPID = "dde3d61a0411511d"
    # 老源同款 UA（实测可过网宿挑战；不要随意加长，长 UA 反而触发更严校验）
    UA_PC = "Mozilla/5.0 Chrome/120"
    UA_M = ("Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36")
    UA_API = "Mozilla/5.0 Chrome/120.0.0.0"
    H_PC = {"User-Agent": UA_PC,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"}
    H_M = {"User-Agent": UA_M,
           "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
           "Referer": "https://m.1905.com/"}
    H_API = {"User-Agent": UA_API, "Referer": "https://m.1905.com/", "Accept": "*/*"}

    TTL_HTML = 300
    TTL_RESOLVE = 240
    TTL_CLEAN = 240
    CACHE_MAX = 30

    # 老源同款分类表（type_id 即 www 站列表路径段）
    CATEGORIES = [
        {"type_id": "list/n_1/o3", "type_name": "电影"},
        {"type_id": "list/n_2/o3", "type_name": "系列电影"},
        {"type_id": "list/a_1/o3", "type_name": "内地"},
        {"type_id": "list/a_2/o3", "type_name": "港台"},
        {"type_id": "list/a_4/o3", "type_name": "欧美"},
        {"type_id": "list/c_178/o3", "type_name": "独家"},
        {"type_id": "list/n_1_t_14/o3", "type_name": "爱情"},
        {"type_id": "list/n_1_t_5/o3", "type_name": "动作"},
        {"type_id": "list/n_1_t_16/o3", "type_name": "科幻"},
        {"type_id": "list/n_1_t_17/o3", "type_name": "恐怖"},
        {"type_id": "list/n_1_t_18/o3", "type_name": "历史"},
        {"type_id": "list/n_1_t_25/o3", "type_name": "喜剧"},
        {"type_id": "list/n_1_t_27/o3", "type_name": "悬疑"},
        {"type_id": "list/n_1_t_36/o3", "type_name": "经典"},
        {"type_id": "list/n_1_t_37/o3", "type_name": "灾难"},
    ]

    def init(self, extend=""):
        # 单例复用：每次 init 全量重置状态（§2.1/§2.13）
        self._html_cache = {}
        self._html_lock = threading.Lock()
        self._resolve_cache = {}
        self._clean_cache = {}
        self._m_home_cache = None
        self._m_home_time = 0.0

    # ==================== 网络 ====================
    def _get_html(self, url, hdr=None, timeout_ms=12000, retry_challenge=True):
        """HTML 抓取（buffer=3 取 bytes 自行解码）。
        403 挑战页退避重试一次；仍失败抛可诊断异常（§1.6 不伪装空）。"""
        with self._html_lock:
            item = self._html_cache.get(url)
            if item and time.time() - item[0] < self.TTL_HTML:
                return item[1]
        headers = hdr or self.H_PC
        text = None
        challenged = False
        for attempt in range(2):
            resp = self.net.req(url, {"headers": headers, "timeout": timeout_ms,
                                      "buffer": 3})
            if resp.get("error"):
                time.sleep(0.5)
                continue
            code = resp.get("code")
            content = resp.get("content")
            if isinstance(content, (bytes, bytearray)):
                content = bytes(content).decode("utf-8", "replace")
            content = str(content or "")
            if not isinstance(code, int):
                time.sleep(0.5)
                continue
            if code == 403 and "_jsc_ch_conf" in content:
                challenged = True
                if retry_challenge:
                    time.sleep(1.2)
                    continue
                break
            if not 200 <= code < 300:
                raise RuntimeError("1905 页面请求失败 HTTP %s: %s" % (code, url))
            text = self._decode(content)
            break
        if text is None:
            if challenged:
                raise RuntimeError(
                    "www.1905.com 被网宿反爬挑战(403)，请稍后重试或更换网络环境")
            raise RuntimeError("1905 页面请求失败: %s" % url)
        with self._html_lock:
            if len(self._html_cache) > 12:
                self._html_cache.clear()
            self._html_cache[url] = (time.time(), text)
        return text

    @staticmethod
    def _decode(raw):
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        return raw

    def _fix_url(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.PC_HOST + u
        return u

    def _pic(self, u):
        if not u or not isinstance(u, str):
            return ""
        u = u.strip()
        if u.startswith(("data:", "javascript:")):
            return ""
        return self._fix_url(u)

    def _unescape(self, s):
        return _html.unescape(s or "").strip()

    # ==================== www 列表解析（老源同款） ====================
    def _extract_list(self, html_txt):
        blocks = re.findall(r'<a[^>]*class="pic-pack-outer"[^>]*>.*?</a>', html_txt, re.S)
        out = []
        for b in blocks:
            m = re.search(r'href="[^"]*/vod/play/(\d+)\.shtml[^"]*"', b)
            if not m:
                continue
            vid = m.group(1)
            m2 = re.search(r'<img[^>]*alt="([^"]*)"', b)
            name = self._unescape(m2.group(1)) if m2 else ""
            m3 = re.search(r'<img[^>]*src="([^"]+)"', b)
            img = self._pic(m3.group(1)) if m3 else ""
            m4 = re.search(r'<p[^>]*>([^<]+)<', b)
            desc = self._unescape(m4.group(1)) if m4 else ""
            if not name:
                continue
            if any(x["vod_id"] == vid for x in out):
                continue
            out.append({"vod_id": vid, "vod_name": name, "vod_pic": img, "vod_remarks": desc})
        return out

    def _page_count(self, html_txt, cur):
        nums = [int(n) for n in re.findall(r'o3p(\d+)\.html', html_txt) if n.isdigit()]
        return max(cur, max(nums) if nums else cur)

    def _crawl(self, url, pg=1, hdr=None):
        h = self._get_html(url, hdr)
        return self._extract_list(h), self._page_count(h, pg)

    def _card(self, it):
        return {"vod_id": it["vod_id"], "vod_name": it["vod_name"],
                "vod_pic": it.get("vod_pic", ""), "vod_remarks": it.get("vod_remarks", "")}

    # ==================== m 站降级数据（仅首页兜底用） ====================
    def _m_home_cards(self):
        """www 被挑战时首页兜底：m.1905.com 首页板块中的免费片卡片。"""
        with self._html_lock:
            if self._m_home_cache and time.time() - self._m_home_time < self.TTL_HTML:
                return self._m_home_cache
        h = self.net.req(self.M_HOST + "/", {"headers": self.H_M, "timeout": 12000,
                                             "buffer": 3})
        code = h.get("code")
        content = h.get("content")
        if isinstance(content, (bytes, bytearray)):
            content = bytes(content).decode("utf-8", "replace")
        content = str(content or "")
        out = []
        if isinstance(code, int) and 200 <= code < 300:
            seen = set()
            for m in re.finditer(
                    r'<a[^>]+href="(?:https?:)?//www\.1905\.com/vod/play/(\d+)\.shtml"[^>]*>(.*?)</a>',
                    content, re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                block = m.group(2)
                nm = re.search(r'class="wikiDes"[^>]*>([^<]+)<', block) or \
                     re.search(r'alt="([^"]+)"', block)
                if not nm:
                    continue
                name = self._unescape(nm.group(1))
                pm = re.search(r'(?:data-src|data-lazysrc|src)="([^"]+\.(?:jpg|png|webp)[^"]*)"', block)
                pic = self._pic(pm.group(1)) if pm else ""
                dm = re.search(r'class="wikiDesAss"[^>]*>([^<]+)<', block)
                desc = self._unescape(dm.group(1)) if dm else ""
                seen.add(vid)
                out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic,
                            "vod_remarks": desc})
        if out:
            with self._html_lock:
                self._m_home_cache = out
                self._m_home_time = time.time()
        return out

    # ==================== FongMi 入口 ====================
    def homeContent(self, filter=False):
        result = {"class": self.CATEGORIES}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        try:
            lst, _ = self._crawl(self.PC_HOST + "/vod/", 1)
        except Exception:
            lst = []
        if not lst:
            # W1: www 被挑战时降级 m 站板块，保证首页有内容
            lst = self._m_home_cards()
        return {"list": [self._card(i) for i in lst[:24]]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        p = int(pg) if pg else 1
        seg = tid if str(tid).startswith("list/") else "list/n_1/o3"
        url = "%s/vod/%s.html" % (self.PC_HOST, seg) if p == 1 else \
              "%s/vod/%sp%s.html" % (self.PC_HOST, seg, p)
        lst, pc = self._crawl(url, p)
        return {"list": [self._card(i) for i in lst], "page": p, "pagecount": pc,
                "limit": 24}

    def searchContent(self, key, quick=False, pg="1"):
        p = int(pg) if pg else 1
        if p > 1:
            # m 站搜索无翻页参数（实测 page=2 与第 1 页相同）
            return {"list": [], "page": p, "pagecount": 1, "limit": 20, "total": 0}
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        text = self._get_html(self.M_HOST + "/m/search?q=" + quote(kw), self.H_M)
        idx = text.find("moiveResources-module")
        blocks = re.findall(r'<li>.*?</li>', text[idx:] if idx >= 0 else text, re.S)
        out = []
        for b in blocks:
            # 实测：搜索结果链接为 play/{id}.shtml 或 mdb/film/{id}
            # 只有 play/ 开头的可播；/mdb/film/ 是资料页无正片
            m = re.search(r'play/(\d+)\.shtml', b)
            if not m or "/mdb/" in b[:b.find("play/")]:
                continue
            vid = m.group(1)
            m2 = re.search(r'<img[^>]*src="([^"]+)"', b)
            img = self._pic(m2.group(1)) if m2 else ""
            m3 = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S)
            name = self._unescape(re.sub(r'<[^>]+>', '', m3.group(1))) if m3 else ""
            m4 = re.findall(r'<dd>([^<]*)</dd>', b)
            desc = " | ".join([self._unescape(x) for x in m4 if x.strip()])
            if name and not any(x["vod_id"] == vid for x in out):
                out.append({"vod_id": vid, "vod_name": name, "vod_pic": img,
                            "vod_remarks": desc})
        return {"list": [self._card(i) for i in out], "page": 1, "pagecount": 1,
                "limit": 20, "total": len(out)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        m = re.search(r"(\d+)", vid)
        if not m:
            return {"list": []}
        vid = m.group(1)
        vod_name = vod_pic = vod_content = vod_year = vod_type = vod_actor = ""
        h = self._get_html("%s/vod/play/%s.shtml" % (self.PC_HOST, vid), self.H_PC)
        if h:
            m = re.search(r'<h1[^>]*playerBox-info-name[^>]*>([^<]+)</h1>', h)
            if m:
                vod_name = self._unescape(m.group(1)).strip()
            else:
                m = re.search(r'<h1[^>]*>([^<]+)</h1>', h)
                if m:
                    vod_name = self._unescape(m.group(1)).strip()
            m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', h, re.I)
            vod_pic = self._pic(m.group(1)) if m else ""
            m = re.search(r'id="playerBoxIntroCon"[^>]*>(.*?)</span>', h, re.DOTALL)
            if m:
                intro = re.sub(r'<[^>]+>', ' ', m.group(1))
                intro = self._unescape(intro)
                intro = re.sub(r'\[详细\]|\.\.\.|\u2026', '', intro)
                intro = re.sub(r'\s+', ' ', intro).strip()
                vod_content = intro
            else:
                m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', h, re.I)
                if m:
                    vod_content = re.sub(r'\.\.\.$', '', self._unescape(m.group(1))).strip()
            m = re.search(r'playerBox-info-year[^>]*>\s*\((\d{4})\)', h)
            if not m:
                m = re.search(r'playerBox-info-year[^>]*>(\d{4})', h)
            if m:
                vod_year = m.group(1)
            m = re.search(r'playerBox-info-area[^>]*>([^<]+)<', h)
            if m:
                vod_type = self._unescape(m.group(1))
            m = re.search(r'playerBox-info-actor[^>]*>([^<]+)<', h)
            if m:
                vod_actor = self._unescape(m.group(1))
        return {"list": [{
            "vod_id": vid,
            "vod_name": vod_name or ("1905 #%s" % vid),
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_year": vod_year,
            "vod_type": vod_type,
            "vod_actor": vod_actor,
            "vod_play_from": "1905",
            # 规范 §1.3: 播放值放稳定 vid，playerContent 才解析真实地址
            "vod_play_url": "正片$%s" % vid,
        }]}

    # ==================== 播放 ====================
    def _sign(self, params):
        parts = ["%s=%s" % (k, quote(str(params[k]), safe="")) for k in sorted(params)]
        return hashlib.sha1(("&".join(parts) + "." + self.APPID).encode("utf-8")).hexdigest()

    def _resolve_play(self, vid, quality="uhd"):
        """签名 API 换真实地址（老源同款）。失败返回 ""。"""
        with self._html_lock:
            item = self._resolve_cache.get(vid)
            if item and time.time() - item[0] < self.TTL_RESOLVE:
                return item[1]
        nonce = int(time.time() * 1000)
        p = {
            "cid": str(vid),
            "nonce": str(nonce),
            "expiretime": str(nonce + 600000),
            "uuid": str(_uuid.uuid4()),
            "playerid": str(int(time.time() * 1000))[1:],
            "page": "https://m.1905.com/m/vod/play/%s.shtml" % vid,
            "type": "hls",
        }
        p["signature"] = self._sign(p)
        qs = "&".join("%s=%s" % (k, quote(str(p[k]), safe="")) for k in p)
        real = ""
        resp = self.net.req("%s/mvod/getVideoinfo.php?%s&callback=cb" % (self.API_HOST, qs),
                            {"headers": self.H_API, "timeout": 12000, "buffer": 3})
        code = resp.get("code")
        content = resp.get("content")
        if isinstance(content, (bytes, bytearray)):
            content = bytes(content).decode("utf-8", "replace")
        if not resp.get("error") and isinstance(code, int) and 200 <= code < 300 and content:
            m = re.search(r'cb\((\{.*\})\)', content, re.S)
            if m:
                try:
                    d = json.loads(m.group(1))
                except Exception:
                    d = {}
                if d.get("StatusCode") == 200:
                    data = d.get("data") or {}
                    path_map = data.get("path") or {}
                    host_map = data.get("quality") or {}
                    for q in (quality, "uhd", "hd", "sd", "ld"):
                        if q in path_map and q in host_map and host_map[q].get("host"):
                            real = host_map[q]["host"] + path_map[q]["path"]
                            break
                    if not real:
                        for q in path_map:
                            if q in host_map and host_map[q].get("host"):
                                real = host_map[q]["host"] + path_map[q]["path"]
                                break
        if real:
            with self._html_lock:
                if len(self._resolve_cache) > 60:
                    self._resolve_cache.clear()
                self._resolve_cache[vid] = (time.time(), real)
        return real

    def playerContent(self, flag, id, vipFlags=None):
        vid = str(id or "").strip()
        m = re.search(r"(\d+)", vid)
        if not m:
            return {"parse": 0, "url": ""}
        vid = m.group(1)
        url = self._resolve_play(vid)
        header = json.dumps({"User-Agent": self.UA_API, "Referer": "https://m.1905.com/"})
        if not url:
            # V1: VIP 片（API 404）或解析失败 -> parse:1 兜底 www 播放页
            return {"parse": 1,
                    "url": "https://www.1905.com/vod/play/%s.shtml" % vid,
                    "header": header}
        if ".m3u8" in url:
            url = self.proxyUrl({"u": url})
            result = {"parse": 0, "url": url, "header": header,
                      "format": "application/x-mpegURL"}  # §2.6.2 逐字
        else:
            result = {"parse": 0, "url": url, "header": header}
        return result

    def isVideoFormat(self, url):
        path = str(url or "").split("?")[0].lower()
        return path.endswith((".m3u8", ".mp4", ".flv"))

    def manualVideoCheck(self):
        return False

    # ==================== 本地代理（P1: 变体跟进 + 绝对 URI） ====================
    @staticmethod
    def _pick_variant(text, base_url):
        best, best_bw = None, -1
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            m = re.search(r"BANDWIDTH=(\d+)", line)
            bw = int(m.group(1)) if m else 0
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if not nxt.startswith("#"):
                    if bw > best_bw:
                        best = urljoin(base_url, nxt)
                        best_bw = bw
                    break
                break
        return best

    def _fetch_m3u8_text(self, url):
        resp = self.net.req(url, {"headers": self.H_API, "timeout": 15000, "buffer": 3})
        code = resp.get("code")
        if resp.get("error") or not isinstance(code, int) or not 200 <= code < 300:
            return None
        content = resp.get("content")
        if isinstance(content, (bytes, bytearray)):
            content = bytes(content).decode("utf-8", "replace")
        text = str(content or "")
        if not text.lstrip().startswith("#EXTM3U"):
            return None
        return text

    def proxy(self, params):
        url = str((params or {}).get("u") or "").strip()
        if not url:
            return [400, "text/plain; charset=utf-8", "missing u", {}]
        with self._html_lock:
            item = self._clean_cache.get(url)
            if item and time.time() - item[0] < self.TTL_CLEAN:
                return [200, "application/vnd.apple.mpegurl", item[1],
                        {"Cache-Control": "no-store"}]
        text = self._fetch_m3u8_text(url)
        if text is None:
            return [502, "text/plain; charset=utf-8", "upstream error", {}]
        base = url.rsplit("/", 1)[0] + "/"
        hops = 0
        while "#EXT-X-STREAM-INF" in text and hops < 3:
            variant = self._pick_variant(text, base)
            if not variant:
                break
            vtext = self._fetch_m3u8_text(variant)
            if vtext is None:
                break
            text = vtext
            base = variant.rsplit("/", 1)[0] + "/"
            hops += 1
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                out.append(line)
            elif s.startswith(("http://", "https://")):
                out.append(s)
            elif s.startswith("//"):
                out.append("https:" + s)
            else:
                out.append(urljoin(base, s))
        cleaned = "\n".join(out) + "\n"
        with self._html_lock:
            if len(self._clean_cache) > self.CACHE_MAX:
                self._clean_cache.clear()
            self._clean_cache[url] = (time.time(), cleaned)
        return [200, "application/vnd.apple.mpegurl", cleaned,
                {"Cache-Control": "no-store"}]

    def destroy(self):
        self._html_cache = {}
        self._resolve_cache = {}
        self._clean_cache = {}
        self._m_home_cache = None
