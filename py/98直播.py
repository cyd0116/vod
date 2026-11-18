# -*- coding: utf-8 -*-
"""
98直播吧 · OK影视 py 采集规则
网站：https://m.98zb.com/
骨架：严格照「OK影视一键写py升级版.py」里的 UNIVERSAL_PY_TEMPLATE（Spider 接口）
      + 三个样例（cctv电影 / 央视频 / 瓜子APP）的零网络首页写法

★ 重要设计：homeContent 完全不发网络请求，分类永远静态返回。
  OK影视 加载 py 源时若首页抓网超时，会把整个源判死并缓存，
  表现就是「连分类都没有」。所有抓网只在用户点分类/详情/播放时发生。

★ 微博录像需会话：在下面 WB_COOKIE 粘入浏览器整串 Cookie 即可自动取 1080P。
"""

import base64
import gzip
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import zlib

sys.path.append('..')

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = object


# ======================================================================
# ★★ 若微博分节录像播不了，只改这一行 ★★
#   电脑浏览器打开那条微博（能播就行）→ F12 → Network →
#   点任意 weibo.com 请求 → Headers → 复制整串 Cookie → 粘进引号内。
#   例：WB_COOKIE = "SUB=_2AkM...; SUBP=0033Wr...; XSRF-TOKEN=..."
# ======================================================================
WB_COOKIE = ""

BASES = ["https://m.98zb.com", "https://m.98zhibo.com",
         "https://www.98zhibo.com", "https://www.98zb.com"]
SITE = BASES[0]
UA = ("Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
WB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 5

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE
try:
    _ctx.set_ciphers("ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                     "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
                     "ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:"
                     "AES256-GCM-SHA384")
except Exception:
    pass

# 静态分类：名称与站点导航一致；第三项是学习失败时的兜底路径
CATS = [
    ("today",       "今日视频",   ""),
    ("live",        "直播",       ""),
    ("nba",         "NBA录像",    "/nbalx/"),
    ("zuqiu",       "足球录像",   "/zqlx/"),
    ("cba",         "CBA录像",    "/cbalx/"),
    ("zonghe",      "综合录像",   "/zhlx/"),
    ("nbajj",       "NBA集锦",    "/nbajj/"),
    ("zuqiujj",     "足球集锦",   "/zqjj/"),
    ("cbajj",       "CBA集锦",    "/cbajj/"),
    ("nbaqx",       "篮球球星",   "/nbaqx/"),
    ("zuqiuqx",     "足球球星",   "/zqqx/"),
    ("nba2",        "NBA",        "/nba/"),
    ("zuqiu2",      "足球",       "/zuqiu/"),
    ("cba2",        "CBA",        "/cba/"),
    ("zonghe2",     "综合",       "/zonghe/"),
    ("mobile",      "手机版",     "/"),
    ("diag",        "源自检",     ""),
]
CAT_NAME = {k: n for k, n, _p in CATS}

_HREF_RE = re.compile(
    r'<a\b[^>]*?href\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([\s\S]*?)</a>',
    re.I)
_TAG_RE = re.compile(r'<[^>]+>')
_M3U8_RE = re.compile(r'https?://[^\s"\'<>\\)]+\.(?:m3u8|mp4|flv|m4v)(?:\?[^\s"\'<>\\)]*)?', re.I)
_EP_RE = re.compile(r'录像|回放|集锦|精华|第[一二三四1-4]节|加时|全场|完整版', re.I)
_EP_SKIP = re.compile(r'统计|公众号|QQ群|淘宝|京东|优惠|电影票|小程序|'
                      r'上一篇|下一篇|更多|首页|末页|下一页|友情链接|免责', re.I)


# ======================================================================
# 工具
# ======================================================================
def _host(u):
    try:
        return urllib.parse.urlsplit(u).netloc.lower()
    except Exception:
        return ""


def _is98(u):
    h = _host(u)
    return ("98zb.com" in h) or ("98zhibo.com" in h) or (not h)


def _is_weibo(u):
    return bool(re.search(r'(^|\.)weibo\.(com|cn)$|weibocdn\.com$',
                          _host(u), re.I))


def _unescape(s):
    s = str(s or "")
    for a, b in (("\\/", "/"), ("\\u002F", "/"), ("\\u003A", ":"),
                 ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def _text(s):
    s = _TAG_RE.sub(" ", str(s or ""))
    s = _unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _abs(u, base=""):
    u = _unescape((u or "").strip())
    if not u or u.startswith(("javascript:", "mailto:", "#")):
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    return urllib.parse.urljoin(base or SITE + "/", u)


def _links(html, base=""):
    out = []
    for a, b, c, inner in _HREF_RE.findall(html or ""):
        href = a or b or c or ""
        u = _abs(href, base)
        if u:
            out.append((u, _text(inner), href))
    return out


def _enc(s):
    """把 URL 编成 OK影视 播放列表里安全的一段（不含 # $ & =）。"""
    return "u" + base64.urlsafe_b64encode(
        str(s or "").encode("utf-8", "ignore")).decode("ascii").rstrip("=")


def _dec(s):
    s = str(s or "").strip()
    if "$" in s:
        s = s.split("$", 1)[1].strip()
    if s.startswith("u") and len(s) > 1:
        try:
            return base64.urlsafe_b64decode(
                s[1:] + "=" * (-len(s[1:]) % 4)).decode("utf-8", "ignore")
        except Exception:
            return s
    return s


def _decode(raw, ct):
    m = re.search(r"charset=([\w-]+)", ct or "", re.I)
    enc = m.group(1).lower() if m else ""
    if not enc:
        m = re.search(r'charset\s*=\s*["\']?([\w-]+)',
                      raw[:2048].decode("ascii", "ignore"))
        enc = m.group(1).lower() if m else "utf-8"
    if enc in ("gb2312", "gbk"):
        enc = "gb18030"
    try:
        s = raw.decode(enc, errors="ignore")
    except Exception:
        s = raw.decode("utf-8", errors="ignore")
    if s.count("\ufffd") > 20:
        try:
            s2 = raw.decode("gb18030", errors="ignore")
            if s2.count("\ufffd") < s.count("\ufffd"):
                s = s2
        except Exception:
            pass
    return s


def _fetch(url, ref=None, timeout=0, alt=True):
    """返回 (html, final_url)。只请求一次；98 域失败时可轮换备用域。"""
    url = _abs(url)
    if not url:
        return "", ""
    cands = [url]
    if alt and _is98(url):
        sp = urllib.parse.urlsplit(url)
        for b in BASES[1:3]:
            bh = urllib.parse.urlsplit(b)
            if bh.netloc and bh.netloc != sp.netloc:
                cands.append(urllib.parse.urlunsplit(
                    (sp.scheme or "https", bh.netloc, sp.path, sp.query, "")))
    for cu in cands:
        try:
            headers = {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Referer": ref or (SITE + "/"),
                "Connection": "close",
            }
            req = urllib.request.Request(cu, headers=headers)
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=_ctx))
            with opener.open(req, timeout=(timeout or TIMEOUT)) as r:
                raw = r.read()
                ce = (r.headers.get("Content-Encoding") or "").lower()
                if ce == "gzip":
                    raw = gzip.decompress(raw)
                elif ce == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                return _decode(raw, r.headers.get("Content-Type") or ""), r.geturl()
        except Exception:
            continue
    return "", ""


def _clean(t):
    t = _text(t)
    t = re.sub(r"\s*[-_|]\s*98直播吧.*$", "", t).strip()
    return t[:90]


# ======================================================================
# 微博：正文页是懒加载，流地址在点播放按钮后由 JS 调接口生成。
#       py 必须自己建会话 + 调 ajax/statuses/show / tv/api/component。
# ======================================================================
_WB_VISITOR = ""
_WB_LOG = []
_B62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _bid_to_mid(bid):
    try:
        out = ""
        for i in range(len(bid) - 4, -4, -4):
            seg = bid[max(i, 0):i + 4]
            v = 0
            for ch in seg:
                v = v * 62 + _B62.index(ch)
            part = str(v)
            out = (part.zfill(7) if i > 0 else part) + out
        return out
    except Exception:
        return ""


def _weibo_ids(url):
    p = urllib.parse.urlsplit(url)
    bid = (p.path.rstrip("/").split("/")[-1] or "").replace(".html", "")
    m = re.search(r"1034[:/](\w{6,48})", url)
    if m:
        o = m.group(1)
        return (o if o.isdigit() else _bid_to_mid(o)), bid, o
    if bid.isdigit() and len(bid) >= 10:
        return bid, bid, bid
    return _bid_to_mid(bid), bid, bid


def _wb_req(url, data=None, ref="https://weibo.com/", ajax=False, timeout=4):
    h = {"User-Agent": WB_UA, "Accept-Language": "zh-CN,zh;q=0.9",
         "Accept": ("application/json, text/plain, */*" if ajax
                    else "text/html,application/xhtml+xml,*/*;q=0.8"),
         "Referer": ref}
    if ajax:
        h["X-Requested-With"] = "XMLHttpRequest"
    if data is not None:
        h["Origin"] = "https://weibo.com"
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    ck = WB_COOKIE or _WB_VISITOR
    if ck:
        h["Cookie"] = ck
        if ajax:
            mx = re.search(r"(?:^|;\s*)XSRF-TOKEN=([^;]+)", ck)
            if mx:
                h["X-XSRF-TOKEN"] = urllib.parse.unquote(mx.group(1))
    try:
        body = data.encode("utf-8") if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, headers=h)
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPSHandler(context=_ctx))
        with op.open(req, timeout=timeout) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


def _visitor():
    """genvisitor → incarnate 换匿名游客 SUB/SUBP。"""
    global _WB_VISITOR
    if WB_COOKIE or _WB_VISITOR:
        return
    try:
        fp = urllib.parse.quote(json.dumps(
            {"os": "1", "browser": "Chrome124,0,0,0", "fonts": "undefined",
             "screenInfo": "1920*1080*24", "plugins": ""}, separators=(",", ":")))
        b1 = _wb_req("https://passport.weibo.com/visitor/genvisitor"
                     "?cb=gen_callback&fp=" + fp + "&from=weibo",
                     ref="https://passport.weibo.com/visitor/visitor", timeout=3)
        mt = re.search(r'"tid"\s*:\s*"([^"]+)"', b1 or "")
        if not mt:
            return
        b2 = _wb_req("https://passport.weibo.com/visitor/visitor?a=incarnate&t="
                     + urllib.parse.quote(mt.group(1), safe="")
                     + "&w=3&c=095&cb=restore_back&from=weibo",
                     ref="https://passport.weibo.com/visitor/visitor", timeout=3)
        sub = re.search(r'"sub"\s*:\s*"([^"]+)"', b2 or "")
        subp = re.search(r'"subp"\s*:\s*"([^"]+)"', b2 or "")
        if sub:
            _WB_VISITOR = "SUB=" + sub.group(1)
            if subp:
                _WB_VISITOR += "; SUBP=" + subp.group(1)
    except Exception:
        pass


def _qscore(label, key, url):
    t = (str(label) + " " + str(key) + " " + str(url)).lower()
    if "1080" in t:
        return 100
    if "4k" in t or "2160" in t:
        return 98
    if "720" in t or "hd" in t:
        return 90
    if "480" in t or "360" in t or "sd" in t:
        return 40
    return 70


def _stream_ok(v):
    v = (v or "").strip()
    return (len(v) > 12 and (v.startswith("http") or v.startswith("//"))
            and re.search(r"\.(?:mp4|m3u8|flv|m4v)(?:\?|$)", v, re.I))


def _json_streams(node, ctx="", out=None):
    """递归收集 JSON 里的流地址；清晰度取自字典 key 或同层 label。"""
    if out is None:
        out = []
    if len(out) > 40:
        return out
    if isinstance(node, dict):
        local = ctx
        for k, v in node.items():
            if isinstance(v, str) and str(k).lower() in (
                    "quality_label", "quality_desc", "label", "definition",
                    "name", "mime") and len(v) < 40:
                local = (local + " " + v).strip()
        for k, v in node.items():
            kl = str(k)
            tag = kl if re.search(r"1080|720|480|hd|sd|mp4|quality|label",
                                  kl, re.I) else local
            if isinstance(v, str) and _stream_ok(v):
                out.append((_qscore(tag, kl, v), tag, _abs(_unescape(v))))
            elif isinstance(v, (dict, list)):
                _json_streams(v, tag or local, out)
    elif isinstance(node, list):
        for x in node:
            _json_streams(x, ctx, out)
    return out


def _weibo_pick(body, base):
    """从响应文本里挑最高清晰度（最多解析 3 个 JSON 起点 + 正则兜底）。"""
    s = _unescape(body or "")
    out = []
    dec = json.JSONDecoder()
    starts = []
    st = s.lstrip()
    if st[:1] in ("{", "["):
        starts.append(len(s) - len(st))
    for kw in ("playback_list", "Component_Play_Playinfo", "media_info"):
        i = s.find('"' + kw + '"')
        if i >= 0:
            j = s.rfind("{", max(0, i - 300), i)
            if j >= 0:
                starts.append(j)
    for i in starts[:3]:
        try:
            obj, end = dec.raw_decode(s, i)
            if end > i + 40:
                out += _json_streams(obj)
        except Exception:
            pass
    # 具名字段（m.weibo.cn 的 stream_url_hd 等）
    for key in ("stream_url_hd", "mp4_hd_url", "mp4_1080p_url",
                "stream_url", "mp4_sd_url"):
        for m in re.finditer(r'"%s"\s*:\s*"([^"]{8,900})"' % key, s, re.I):
            u = _abs(_unescape(m.group(1)), base)
            if u:
                out.append((_qscore(key, key, u), key, u))
    for m in _M3U8_RE.finditer(s):
        out.append((_qscore("", "", m.group(0)), "", m.group(0)))
    seen, res = set(), []
    for sc, lab, u in sorted(out, key=lambda x: -x[0]):
        if u and u not in seen:
            seen.add(u)
            res.append((sc, lab, u))
    return res


def _weibo_resolve(url):
    """返回 (最优直链, 清晰度分, 日志列表)。"""
    global _WB_VISITOR
    log = []
    _WB_LOG[:] = log
    mid, bid, media = _weibo_ids(url)
    log.append("bid=%s mid=%s" % (bid, mid or "?"))  # noqa
    if WB_COOKIE:
        log.append("Cookie: 文件顶部 WB_COOKIE 已填")
    elif _WB_VISITOR:
        log.append("Cookie: 已缓存游客会话")
    else:
        _visitor()
        log.append("游客会话: " + ("OK" if _WB_VISITOR else
                    "失败 → 请填 WB_COOKIE"))

    page = _wb_req(url, ref="https://weibo.com/", timeout=4)
    oids = []
    if page:
        for m in re.finditer(r"1034[:/]([A-Za-z0-9]{8,48})", _unescape(page)):
            o = "1034:" + m.group(1)
            if o not in oids:
                oids.append(o)
        log.append("正文页 len=%d oid=%s" % (len(page),
                   ",".join(oids[:2]) or "无"))
    if mid and ("1034:" + mid) not in oids:
        oids.append("1034:" + mid)

    aj = lambda i: ("https://weibo.com/ajax/statuses/show?id=" + i +
                    "&locale=zh-CN&isGetLongText=true")
    sources = []
    if mid:
        sources.append(("ajax/mid", "GET", aj(mid)))
    if bid and bid != mid:
        sources.append(("ajax/bid", "GET", aj(bid)))
    if oids:
        oid = oids[0]
        payload = urllib.parse.urlencode({
            "data": json.dumps({"Component_Play_Playinfo": {"oid": oid}},
                               separators=(",", ":")),
            "page": "/tv/show/" + oid})
        sources.append(("tv/component", "POST",
                        "https://weibo.com/tv/api/component?page=" +
                        urllib.parse.quote("/tv/show/" + oid, safe="/:"),
                        payload, "https://weibo.com/tv/show/" + oid))
    if mid:
        sources.append(("m/statuses", "GET",
                        "https://m.weibo.cn/statuses/show?id=" + mid))
    sources.append(("pc正文页", "GET", url))

    best, sc, lab, auth_fail = "", 0, "", False
    for item in sources:
        name, kind, arg = item[0], item[1], item[2]
        if auth_fail and "m.weibo.cn" not in arg:
            continue
        try:
            if kind == "POST":
                body = _wb_req(arg, data=item[3], ref=item[4], ajax=True)
            elif arg == url and page:
                body = page
            else:
                body = _wb_req(arg, ref=("https://m.weibo.cn/"
                                         if "m.weibo.cn" in arg
                                         else "https://weibo.com/"),
                               ajax=name.startswith("ajax/"), timeout=3)
            if not body:
                log.append("%-13s 无响应" % name)
                continue
            if re.search(r'"ok"\s*:\s*-?100|login\.php|visitor/visitor',
                         body[:400], re.I):
                log.append("%-13s 需登录(缺Cookie)" % name)
                auth_fail = True
                continue
            c = _weibo_pick(body, arg)
            log.append("%-13s len=%-6d 流=%d 最佳=%s" %
                       (name, len(body), len(c),
                        (c[0][1] or c[0][2][:40]) if c else "无"))
            if c and c[0][0] > sc:
                best, sc, lab = c[0][2], c[0][0], c[0][1]
            if sc >= 100:
                break
        except Exception as e:
            log.append("%-13s 异常 %s" % (name, str(e)[:40]))
    if not best:
        log.append("结论: 未取到直链，请填 WB_COOKIE 后重启")
    return best, sc, log


# ======================================================================
# Spider —— 接口与模板 / 样例逐字对齐
# ======================================================================
class Spider(_BaseSpider):

    VERSION = "98直播吧 v5.0（模板骨架·首页零网络）"

    def __init__(self):
        if _BaseSpider is not object:
            try:
                _BaseSpider.__init__(self)
            except Exception:
                pass
        self.inited = False
        self.learned = False
        self.cat_url = {}
        self.home_cache = None

    def getName(self):
        return "98直播吧┃[py]"

    def init(self, extend=""):
        """★ 纯配置解析，绝不抓网（模板会在 init 里探测接口，但 98 站不需要）。"""
        if self.inited:
            return
        self.inited = True
        if not extend:
            return
        try:
            cfg = extend if isinstance(extend, dict) else json.loads(str(extend))
        except Exception:
            return
        b = cfg.get("base") or cfg.get("site")
        if b:
            if not str(b).startswith("http"):
                b = "https://" + str(b)
            BASES.insert(0, str(b).rstrip("/"))

    # ------------------------------------------------------------------
    def homeContent(self, filter):
        """★ 照 cctv电影 / 瓜子APP 样例：纯静态，一个网络请求都不发。
        这是「分类一定显示」的唯一保证。"""
        result = {"class": [{"type_name": n, "type_id": k}
                            for k, n, _p in CATS]}
        if filter:
            result["filters"] = {
                "live": [{"key": "g", "name": "赛事", "value": [
                    {"n": "全部", "v": ""}, {"n": "足球", "v": "足球"},
                    {"n": "篮球", "v": "篮球"}, {"n": "NBA", "v": "NBA"},
                    {"n": "CBA", "v": "CBA"}, {"n": "综合", "v": "综合"}]}]}
        return result

    def homeVideoContent(self):
        """首页推荐同样不抓网：内容由「今日视频」分类提供。"""
        return {"list": []}

    # ------------------------------------------------------------------
    def _home(self, timeout=4):
        if self.home_cache is not None:
            return self.home_cache
        h, f = _fetch(SITE + "/", timeout=timeout)
        self.home_cache = (h, f)
        return self.home_cache

    def _learn(self):
        """点分类时才抓首页，从导航 <a> 学真实栏目 URL（不猜路径）。"""
        if self.learned:
            return
        self.learned = True
        html, final = self._home()
        if not html:
            return
        for href, text, _raw in _links(html, final):
            for k, name, _p in CATS:
                if k in ("today", "live", "diag") or k in self.cat_url:
                    continue
                if text == name or (len(text) <= len(name) + 2 and name in text):
                    self.cat_url[k] = href
                    break

    def _items(self, html, base):
        """提取录像条目（带日期 / 全场录像 / 集锦）。"""
        out, seen = [], set()
        for href, text, _raw in _links(html, base):
            t = _clean(text)
            if not t or len(t) < 9 or len(t) > 95:
                continue
            if not re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月", t):
                continue
            if not re.search(r"录像|回放|集锦|十佳|精华|全场", t):
                continue
            if _EP_SKIP.search(t) or href in seen:
                continue
            if not _is98(href):
                continue
            seen.add(href)
            date = ""
            dm = re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月\d{1,2}日", t)
            if dm:
                date = dm.group(0)
            out.append({"vod_id": _enc(href), "vod_name": t,
                        "vod_pic": "",
                        "vod_remarks": (date + " · 录像") if date else "录像"})
        return out

    def _live(self, html, base):
        """从首页赛程里提取直播线路（无插件优先）。"""
        out, seen = [], set()
        for href, text, _raw in _links(html, base):
            t = _text(text)
            if not t or len(t) > 30:
                continue
            if not re.search(r"直播|无插件|插件|网页", t) or "比分直播" in t:
                continue
            if href in seen or not href.startswith("http"):
                continue
            seen.add(href)
            out.append({"vod_id": _enc(href), "vod_name": t,
                        "vod_pic": "", "vod_remarks": "直播线路"})
        return out[:16]

    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        """★ 网络操作只在这里（用户主动点分类才触发），全程 try + 短超时。"""
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        result = {"list": [], "page": page, "pagecount": 1,
                  "limit": 24, "total": 0}
        try:
            tid = str(tid)
            ext = extend if isinstance(extend, dict) else {}
            if tid == "diag":
                return {"list": [{"vod_id": "diag",
                                  "vod_name": "源自检 · 点开看配置与取流日志",
                                  "vod_pic": "", "vod_remarks": "排障用"}],
                        "page": 1, "pagecount": 1, "limit": 1, "total": 1}

            html, final = self._home(timeout=4)
            if not html:
                return result

            self._learn()
            if tid == "live":
                items = self._live(html, final)
                g = str(ext.get("g") or "")
                if g:
                    items = [x for x in items if g in x["vod_name"]] or items
                result.update({"list": items, "limit": max(len(items), 1),
                               "total": max(len(items), 1)})
                return result
            if tid == "today":
                items = self._items(html, final)[:60]
                result.update({"list": items, "limit": max(len(items), 1),
                               "total": max(len(items), 1)})
                return result

            url = self.cat_url.get(tid)
            if not url:
                for k, name, p in CATS:
                    if k == tid and p:
                        url = _abs(p, final or SITE + "/")
                        break
            if url:
                h2, f2 = _fetch(url, ref=final or SITE + "/", timeout=5)
                if h2 and self._items(h2, f2 or url):
                    html, final = h2, (f2 or url)
            items = self._items(html, final)

            # 同一分类页拿不到内容时按分类名做本地过滤，避免所有分类同内容
            kw = CAT_NAME.get(tid, "")
            if kw and len(items) > 8:
                key = re.sub(r"录像|集锦|球星", "", kw).strip()
                if key:
                    hit = [x for x in items if key in x["vod_name"]]
                    if hit:
                        items = hit
            if page > 1:
                nxt = ""
                for href, text, _raw in _links(html, final):
                    if _text(text) in ("下一页", "下页", "»", "末页"):
                        nxt = href
                        break
                if nxt:
                    h3, f3 = _fetch(nxt, ref=final, timeout=5)
                    if h3:
                        items = self._items(h3, f3 or nxt)
                        result["pagecount"] = max(page + 1, 2)
            result.update({"list": items[:60],
                           "limit": max(len(items), 24),
                           "total": max(len(items), 24)})
        except Exception as e:
            result["list"] = [{"vod_id": "err", "vod_name": "分类加载异常",
                               "vod_pic": "", "vod_remarks": str(e)[:60]}]
        return result

    # ------------------------------------------------------------------
    def _episodes(self, html, base):
        """★ 98 的详情页本身就是「下一级目录」：
        [国语回放] 第一节 / [腾讯国语] 全场录像回放 … 每个 <a> 指向外部播放页。"""
        groups, seen = {}, set()
        for href, text, _raw in _links(html, base):
            t = _clean(text)
            if not t or len(t) < 9 or len(t) > 130:
                continue
            if not _EP_RE.search(t) or _EP_SKIP.search(t):
                continue
            if not re.match(r"^\s*[\[【(（][^\]】)）]{1,12}[\]】)）]", t):
                continue
            if not href.startswith("http"):
                continue
            g = re.match(r"^\s*[\[【(（]([^\]】)）]{1,12})[\]】)）]", t).group(1)
            g = g.strip()[:12]
            name = re.sub(r"^\s*[\[【(（][^\]】)）]{1,12}[\]】)）]\s*", "", t)
            short = re.search(r"第[一二三四1-4]节\s*录像|全场录像回放|"
                              r"全场回放|全场集锦|加时|完整版|录像回放|精华回放", name)
            name = (short.group(0) if short else name)[:36]
            key = (g, href)
            if key in seen:
                continue
            seen.add(key)
            groups.setdefault(g, [])
            if len(groups[g]) < 24:
                groups[g].append((name, href))
        return {k: v for k, v in groups.items() if v}

    def detailContent(self, array):
        vid = (str(array[0]) if isinstance(array, (list, tuple))
               else str(array)) if array else ""
        if not vid:
            return {"list": []}
        if vid == "diag":
            lines = ["98直播吧 · 源自检（静态·不发网络请求）",
                     "版本: " + self.VERSION, "",
                     "分类: %d 个，纯静态返回，站点不通也会显示" % len(CATS),
                     "首页策略: homeContent 零网络请求", "",
                     "【微博取流配置】",
                     "文件顶部 WB_COOKIE: " + ("已填" if WB_COOKIE else "未填"),
                     "扩展参数 wb_cookie: " + ("已填" if False else "未填"),
                     "", "【上一次真实取流日志】（点一节录像后再回来）"]
            lines += ["  " + x for x in (_WB_LOG or ["（暂无）"])[-14:]]
            lines += ["", "【若仍不能播 · 只改一行】",
                      "浏览器打开那条微博 → F12 → Network → 点任意 weibo.com 请求",
                      "→ Headers 复制整串 Cookie → 粘进本 py 顶部 WB_COOKIE = \"\"",
                      "→ 保存 → 删除源重新添加 → 重启 OK影视。",
                      "", "【若分类仍为空】",
                      "说明壳缓存了旧版判死的源：删除该源、重新添加、重启。" ]
            return {"list": [{
                "vod_id": "diag", "vod_name": "源自检 · 点开看诊断结果",
                "vod_pic": "", "type_name": "诊断", "vod_year": "",
                "vod_area": "", "vod_remarks": "网络 / 分类 / 播放解析",
                "vod_actor": "", "vod_director": "",
                "vod_content": "\n".join(lines),
                "vod_play_from": "98直播吧",
                "vod_play_url": "回到首页$" + _enc(SITE + "/")}]}

        url = _dec(vid)
        if not url.startswith("http"):
            url = _abs(url, SITE + "/")
        html, final = ("", "")
        try:
            html, final = _fetch(url, ref=SITE + "/", timeout=5)
        except Exception:
            pass

        mt = re.search(r"<title[^>]*>([\s\S]{1,200}?)</title>", html or "", re.I)
        title = _clean(mt.group(1)) if mt else url
        desc = "98直播吧 · 外链资源"

        eps = self._episodes(html, final or url) if html else {}
        if eps:
            # 微博线路排第一组（自动 1080P）；腾讯等官方页需登录鉴权
            def ratio(lst):
                return sum(1 for _n, u in lst if _is_weibo(u)) / float(len(lst) or 1)
            ordered = sorted(eps.items(), key=lambda kv: -ratio(kv[1]))
            shows, urls = [], []
            for g, lst in ordered:
                shows.append(g)
                urls.append("#".join("%s$%s" % (n, _enc(u)) for n, u in lst))
            wb_n = sum(1 for v in eps.values() for _n, u in v if _is_weibo(u))
            desc = ("【本场分节】%d 个线路 / %d 集（微博 %d 集）。"
                    "第一组为微博线路，自动选 1080P 直连；"
                    "腾讯等官方页需登录鉴权，建议优先用第一组。"
                    % (len(eps), sum(len(v) for v in eps.values()), wb_n))
            play_from = "$$$".join(shows)
            play_url = "$$$".join(urls)
        else:
            # 没有分节（直播线路页 / 内嵌播放器页）：交给嗅探或内置解析
            streams = self._sniff(html or "", final or url)
            if streams:
                play_from = "98直连"
                play_url = "#".join("线路%d$%s" % (i + 1, _enc(u))
                                    for i, u in enumerate(streams[:8]))
            else:
                play_from = "原网页播放"
                play_url = "打开播放页$" + _enc(final or url)
                desc += "\n\n未取到明文流，已交给内置解析。"
        return {"list": [{
            "vod_id": vid, "vod_name": title, "vod_pic": "",
            "type_name": "体育", "vod_year": "", "vod_area": "",
            "vod_remarks": "98直播吧 · 外链资源", "vod_actor": "",
            "vod_director": "", "vod_content": desc,
            "vod_play_from": play_from, "vod_play_url": play_url}]}

    @staticmethod
    def _sniff(html, base):
        s = _unescape(html or "")
        out = []
        for m in _M3U8_RE.finditer(s):
            u = m.group(0)
            if u not in out:
                out.append(u)
        for m in re.finditer(r'player_\w+\s*=\s*(\{[\s\S]{0,800}?\})', s):
            try:
                d = json.loads(m.group(1))
                u = _unescape(str(d.get("url") or ""))
                if u and _stream_ok(u) and u not in out:
                    out.append(_abs(u, base))
            except Exception:
                pass
        return out

    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        """本地搜索：从首页 + 已访问分类页缓存的条目里过滤。"""
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": page}
        try:
            html, final = self._home(timeout=4)
            items = self._items(html, final)
            hit = [x for x in items if kw in x["vod_name"]]
            return {"list": hit[:40], "page": page}
        except Exception:
            return {"list": [], "page": page}

    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "").strip()
        url = _dec(raw)
        if not url.startswith("http"):
            url = _abs(url, SITE + "/")
        if not url:
            return {"parse": 0, "url": "", "msg": "地址为空"}

        # 明文直链
        if _stream_ok(url):
            return self._direct(url, url)

        # 微博：主动建会话 + 调接口取 1080P（绝不把懒加载网页交给壳）
        if _is_weibo(url):
            best, sc, log = _weibo_resolve(url)
            if best:
                return self._direct(best, url)
            return {"parse": 0, "url": "", "jx": 0, "header": {},
                    "msg": ("微博直链未取到 → 请在本 py 顶部 WB_COOKIE "
                            "填入浏览器整串 Cookie 后重启。\n" +
                            "\n".join(log[-6:]))}

        # 98 中转页：跟到外部播放页
        if _is98(url):
            h, f = _fetch(url, ref=SITE + "/", timeout=4)
            if h:
                for _href, _t, _r in _links(h, f or url):
                    if _is_weibo(_href):
                        best, sc, log = _weibo_resolve(_href)
                        if best:
                            return self._direct(best, url)
                streams = self._sniff(h, f or url)
                if streams:
                    return self._direct(streams[0], url)
                url = f or url

        # 第三方官方页（腾讯/爱奇艺等）：交壳内置解析
        p = urllib.parse.urlsplit(url)
        return {"parse": 1, "playUrl": "", "url": url, "jx": 1,
                "header": {"User-Agent": UA,
                           "Referer": p.scheme + "://" + p.netloc + "/"},
                "msg": "第三方官方页，若解析不了请改用【国语回放】微博线路"}

    def _direct(self, url, ref):
        low = url.lower().split("?")[0]
        ct = ("application/vnd.apple.mpegurl" if low.endswith(".m3u8")
              else "video/mp4" if low.endswith(".mp4")
              else "video/x-flv" if low.endswith(".flv") else "")
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0,
                "header": {"User-Agent": UA, "Referer": ref or SITE + "/"},
                "contentType": ct}

    # ------------------------------------------------------------------
    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                url = param.get("url") or param.get("path") or ""
            elif isinstance(param, (list, tuple)) and param:
                url = str(param[0])
            else:
                url = str(param or "")
            url = _dec(url.strip())
            if not url.startswith("http"):
                return [404, "text/plain", b"invalid url", {}]
            h, final = _fetch(url, timeout=5)
            if not h:
                return [502, "text/plain", b"upstream failed", {}]
            body = h
            if ".m3u8" in url.lower():
                def fix(m):
                    line = m.group(0)
                    return line if line.startswith(("#", "http", "//")) \
                        else _abs(line, final or url)
                body = re.sub(r"(?m)^[^\s#][^\r\n]*$", fix, h)
            ct = ("application/vnd.apple.mpegurl" if ".m3u8" in url.lower()
                  else "video/MP2T" if ".ts" in url.lower()
                  else "application/octet-stream")
            return [200, ct, body.encode("utf-8", "ignore"),
                    {"Access-Control-Allow-Origin": "*"}]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8", "ignore"), {}]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "destroy"
