# -*- coding: utf-8 -*-
"""
98直播吧 · OK影视(影视仓 / Hipy / drpy / T4) 采集规则
==================================================================
目标站：https://m.98zb.com/  （98直播吧 / 98篮球网）

设计要点
--------
1) 不写死任何详情页 / 播放页 URL。运行时抓取站点真实 HTML，从 a[href]
   中自动发现导航分类、录像条目、直播线路，随站点改版自动跟随。
2) 完整覆盖原站分类：直播赛程（咪咕/CCTV5/腾讯/无插件/插件线路）、
   NBA录像、NBA集锦、篮球球星、CBA录像、CBA集锦、足球录像、
   足球集锦、足球球星、综合体育、手机版四大频道与四大录像频道。
   分类优先用首页导航动态发现，失败时回退到内置路径表。
3) 播放层多层嗅探：m3u8/mp4 明文 → url= 参数 → player_* JSON →
   base64/atob → iframe 递归（最多 3 层）→ 仍拿不到直链则交 OK影视
   内置解析(parse=1)，保证「无插件」线路在电视端可播。
4) 多域名自动兜底：m.98zb.com / www.98zb.com / m.98zhibo.com /
   www.98zhibo.com；任一域返回 403/超时会自动换域重试。
   完整浏览器头 + TLS 指纹模拟 + gzip/deflate + GBK/GB18030 自动识别。
5) 内置「源自检」分类：在 OK影视 里直接看各域连通性、抓到的分类数、
   条目数、线路数以及一条真实线路的解析结果，方便现场验证。

说明：本文件仅供学习交流。98直播吧是网址导航站，所有视听节目均为
第三方外链，资源可用性、合法性与版权由对应资源站负责。
作者：元宝（按用户提供的「一键写PY」模板与三份站点规则改写）
"""
import base64
import gzip
import hashlib
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import zlib

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


# ======================================================================
# 常量 / 网络层
# ======================================================================
BASES = [
    "https://m.98zb.com",        # 用户给的门户：首页 / 赛程
    "https://m.98zhibo.com",     # 录像 / 详情页主域（/nbalx/ 等）
    "https://www.98zhibo.com",
    "https://www.98zb.com",
]
# 录像分类页所在域（DedeCMS 列表 /nbalx/list_175_1.html 等只在这个域）
CAT_BASE = "https://m.98zhibo.com"
UA = ("Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
TIMEOUT = 8
CACHE_TTL = 90
_CACHE = {}
# 可选：从源扩展参数注入 Cookie / UA（应对站点 WAF 要求浏览器会话）
_EXTRA_HEADERS = {}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
try:
    _CTX.set_ciphers(
        "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:"
        "AES256-GCM-SHA384")
except Exception:
    pass
try:
    _CTX.set_alpn_protocols(["http/1.1"])
except Exception:
    pass

_HREF_RE = re.compile(
    r"""<a\b[^>]*?href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>([\s\S]*?)</a>""",
    re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", re.I)
_M3U8_RE = re.compile(
    r"""(?:https?:)?//[^\s"'<>\\)]+?\.(?:m3u8|mp4|flv|mkv|ts)(?:\?[^\s"'<>\\)]*)?""",
    re.I)
_STREAM_EXT = re.compile(r"\.(?:m3u8|mp4|flv|mkv)(?:\?|$)", re.I)


def _unescape(s):
    return (s or "").replace("&amp;", "&").replace("&#38;", "&") \
        .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ") \
        .replace("\\/", "/").replace("\\u002F", "/").replace("\\u0026", "&")


def _text(s):
    s = _SCRIPT_RE.sub(" ", s or "")
    s = _TAG_RE.sub(" ", s)
    s = _unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _abs(u, base=""):
    u = _unescape((u or "").strip())
    if not u or u.startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return (base or BASES[0]).split("/")[0] + "//" + \
            urllib.parse.urlsplit(base or BASES[0]).netloc + u
    b = base or BASES[0]
    if not b.endswith("/"):
        b = b.rsplit("/", 1)[0] + "/"
    return urllib.parse.urljoin(b, u)


def _host(url):
    try:
        return urllib.parse.urlsplit(url).netloc.lower()
    except Exception:
        return ""


def _same_family(url):
    h = _host(url)
    return any(x in h for x in ("98zb.com", "98zhibo.com")) or not h


def _decode(raw, ct):
    charset = ""
    m = re.search(r"charset=([\w-]+)", ct or "", re.I)
    if m:
        charset = m.group(1).lower()
    if not charset:
        head = raw[:2048].decode("ascii", errors="ignore")
        m = re.search(r'charset\s*=\s*["\']?([\w-]+)', head, re.I)
        if m:
            charset = m.group(1).lower()
    if charset in ("gbk", "gb2312", "gb18030"):
        charset = "gb18030"
    elif charset in ("utf-8", "utf8", ""):
        charset = "utf-8"
    try:
        s = raw.decode(charset, errors="ignore")
    except Exception:
        s = raw.decode("utf-8", errors="ignore")
    # DedeCMS 老模板常声明 utf-8 实为 GBK：替换符过多时按 gb18030 重解
    if s.count("\ufffd") > 20:
        try:
            s2 = raw.decode("gb18030", errors="ignore")
            if s2.count("\ufffd") < s.count("\ufffd"):
                s = s2
        except Exception:
            pass
    return s


def _fetch(url, ref=None, retry=1, use_cache=True):
    """返回 (html, final_url)。失败自动换其它备用域名重试。"""
    url = _abs(url)
    if not url:
        return "", ""
    now = time.time()
    ck = url + "|" + (ref or "")
    if use_cache and ck in _CACHE:
        ts, html, final = _CACHE[ck]
        if now - ts < CACHE_TTL:
            return html, final

    candidates = [url]
    sp = urllib.parse.urlsplit(url)
    if _same_family(url):
        for b in BASES:
            bh = urllib.parse.urlsplit(b)
            if bh.netloc and bh.netloc != sp.netloc:
                candidates.append(urllib.parse.urlunsplit(
                    (sp.scheme or "https", bh.netloc, sp.path, sp.query, sp.fragment)))
    else:
        # 外部播放页：保留原域，失败不换 98 域（避免污染外链）
        candidates = [url]

    last = ""
    for cu in candidates[:4]:
        for attempt in range(retry + 1):
            try:
                headers = {
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                              "image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Referer": ref or (urllib.parse.urlunsplit(
                        (urllib.parse.urlsplit(cu).scheme, urllib.parse.urlsplit(cu).netloc,
                         "/", "", ""))),
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin" if ref else "none",
                    "Sec-Fetch-User": "?1",
                    "Connection": "close",
                }
                if _EXTRA_HEADERS:
                    headers.update(_EXTRA_HEADERS)
                req = urllib.request.Request(cu, headers=headers)
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}),
                    urllib.request.HTTPSHandler(context=_CTX))
                with opener.open(req, timeout=TIMEOUT) as r:
                    raw = r.read()
                    enc = (r.headers.get("Content-Encoding") or "").lower()
                    if enc == "gzip":
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            try:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                            except Exception:
                                pass
                    html = _decode(raw, r.headers.get("Content-Type") or "")
                    final = r.geturl()
                if html:
                    if use_cache:
                        _CACHE[ck] = (now, html, final)
                    return html, final
                last = "empty body"
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
                continue
    return "", last


def _links(html, base=""):
    """提取全部 (绝对href, 锚文本)，兼容单/双/无引号。"""
    out = []
    for a, b, c, inner in _HREF_RE.findall(html or ""):
        href = a or b or c or ""
        u = _abs(href, base)
        if u:
            out.append((u, _text(inner), href))
    return out


def _enc(s):
    """把含 # $ & 的 URL 编成 OK影视 播放列表里安全的一段。"""
    if not s:
        return ""
    return "u" + base64.urlsafe_b64encode(
        s.encode("utf-8", errors="ignore")).decode("ascii").rstrip("=")


def _dec(s):
    s = str(s or "").strip()
    if s.startswith("u") and len(s) > 1:
        try:
            pad = "=" * (-len(s[1:]) % 4)
            return base64.urlsafe_b64decode(s[1:] + pad).decode(
                "utf-8", errors="ignore")
        except Exception:
            return s
    return s


def _clean_title(s):
    s = _text(s)
    s = re.sub(r"[-_|]\s*98(?:直播吧|篮球网).*$", "", s)
    s = re.sub(r"\s*[\|｜]\s*.*$", "", s) if len(s) > 40 else s
    return s.strip(" -_|｜")[:70]


def _is_nav_text(t):
    if not t or len(t) > 10:
        return False
    return bool(re.search(r"录像|集锦|球星|直播|综合|体育|NBA|CBA|足球|篮球|"
                         r"电竞|手机版|今日视频|昨天视频|首页|热门", t, re.I))


def _looks_item(href, text):
    """判断一个链接像「内容页」而不是导航/分页。"""
    if not href:
        return False
    t = _text(text)
    if len(t) < 6 or len(t) > 90:
        return False
    if not re.search(r"录像|集锦|十佳球|回放|全场|精华|视频|直播|"
                     r"决赛|常规赛|第\d+轮|小组赛|十佳|球星", t):
        return False
    if re.fullmatch(r"[\d\s./]+", t):
        return False
    # 纯导航/线路文字（NBA录像(手机版)、比分直播、咪咕直播(无插件)…）不算内容条目
    if len(t) <= 16 and not re.search(r"\d", t) and \
            re.search(r"录像|集锦|直播|球星|综合|体育|视频|手机版", t):
        return False
    p = urllib.parse.urlsplit(href)
    tail = p.path.rstrip("/").split("/")[-1] if p.path else ""
    if tail in ("", "index.html", "index.htm") and not p.query:
        return False
    # 纯分页链接 (/shipin/nba/2) 且文字是数字，已被上面挡掉
    return True


# ======================================================================
# 微博视频号解析（98 的分节录像大量指向 weibo.com/<uid>/<bid>）
# 目标：自动挑 1080P，而不是把网页丢给壳随便解析一个默认清晰度
# ======================================================================
def _is_weibo(url):
    h = _host(url)
    return bool(re.search(r"(^|\.)weibo\.(com|cn)$|^video\.weibo\.com$"
                          r"|^f\.video\.weibocdn\.com$|^weibocdn\.com$", h, re.I))


def _is_play_host(url):
    h = _host(url)
    return bool(re.search(
        r"(^|\.)(weibo\.com|weibo\.cn|v\.qq\.com|youku\.com|iqiyi\.com|"
        r"mgtv\.com|bilibili\.com|douyin\.com|kuaishou\.com|"
        r"pptv\.com|le\.com|sohu\.com|163\.com)$", h, re.I))


def _qscore(label="", url="", key=""):
    """清晰度打分：1080P 最高，其次 4K/720P/HD，最后 480P。"""
    t = (str(label) + " " + str(key) + " " + str(url)).lower()
    if "1080" in t:
        return 100
    if "4k" in t or "2160" in t:
        return 98
    if "720" in t or re.search(
            r"\bhd\b|[_/.-]hd[_/.-]|hd_url|url_hd|_hd$|mp4_hd|hd_mp4", t):
        return 90
    if "480" in t or "360" in t or re.search(r"\bsd\b|[_/.-]sd[_/.-]|_sd$", t):
        return 40
    return 70


def _weibo_candidates(html, base):
    """从微博页面收集所有候选流，返回按清晰度降序的 (分数, 标签, URL)。"""
    s = _unescape(html or "")
    out = []

    # ★ 接口返回的是 JSON / JSONP，不是 HTML。用 raw_decode 把文本里所有
    #   JSON 对象抠出来递归解析，覆盖 playback_list、Component_Play_Playinfo
    #   的 urls 字典（{"mp4_1080p":"//...mp4"}）、$render_data 等结构。
    dec = json.JSONDecoder()
    scanned = 0
    for i, ch in enumerate(s[:200000]):
        if ch != "{" or len(out) > 40:
            continue
        try:
            obj, end = dec.raw_decode(s, i)
            if isinstance(obj, (dict, list)) and end > i + 60:
                out += _json_streams(obj, base)
                scanned += 1
        except Exception:
            pass
        if scanned >= 8:
            break

    def push(label, u, key=""):
        u = _unescape((u or "").strip().strip("'\""))
        if not u:
            return
        a = _abs(u, base)
        if not a:
            return
        if not re.search(r"\.(?:mp4|m3u8|flv|m4v|ts)(?:\?|$)", a, re.I) and \
                not re.search(r"weibocdn|video\.weibo|/vod/|/stream/", a, re.I):
            return
        out.append((_qscore(label, a, key), str(label), a))

    # 1) quality_label / definition 与其「最近邻」的 url 配对。
    #    不能用宽窗口收全部 url：否则 1080p 标签会把 480p 的地址也算成 1080P。
    url_pat = (r'"(?:url|play_url|stream_url|mp4_hd_url|stream_url_hd|'
               r'download_url|src)"\s*:\s*"([^"]{8,900})"')
    for qm in re.finditer(
            r'"(?:quality_label|quality|definition|label|name|play_info_label)"'
            r'\s*:\s*"([^"]{1,40})"', s, re.I):
        lab = qm.group(1)
        after = s[qm.end():qm.end() + 420]
        before = s[max(0, qm.start() - 420):qm.start()]
        um = re.search(url_pat, after, re.I)
        if not um:
            ms = list(re.finditer(url_pat, before, re.I))
            um = ms[-1] if ms else None
        if um:
            push(lab, um.group(1))

    # 2) 具名字段（m.weibo.cn/statuses/show 的 media_info 就是这些）
    for key in ("stream_url_hd", "mp4_hd_url", "mp4_1080p_url",
                "stream_url", "mp4_sd_url", "playback_url",
                "video_url", "h5_url", "origin_url"):
        for um in re.finditer(r'"%s"\s*:\s*"([^"]{8,900})"' % key, s, re.I):
            push(key, um.group(1), key)

    # 3) 页面里任意明文媒体地址兜底
    for m in _M3U8_RE.finditer(s):
        push("", m.group(0))

    seen, res = set(), []
    for sc, lab, u in sorted(out, key=lambda x: -x[0]):
        if u in seen:
            continue
        seen.add(u)
        res.append((sc, lab, u))
    return res


def _weibo_pick(html, base):
    """返回 (最优流URL, 清晰度分, 标签)；没有则 ("",0,"")。"""
    c = _weibo_candidates(html, base)
    return (c[0][2], c[0][0], c[0][1]) if c else ("", 0, "")


# ======================================================================
# ★ 关键：微博正文页是懒加载的，不点「播放按钮」HTML 里没有流地址。
#   浏览器中之所以能播，是因为它自动完成了「匿名访客会话」(genvisitor →
#   incarnate 换 SUB/SUBP)，然后点击时由 JS 调 ajax/show 或 tv/api/component
#   生成流地址。脚本必须自己走完这套流程，否则只会拿到登录页 → 一直转圈。
# ======================================================================
WB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_WB_COOKIE = ""          # 自动换到的匿名访客会话（进程内复用）
_WB_USER_COOKIE = ""     # 用户在源扩展参数里填的浏览器 Cookie（优先级最高）
_WB_LOG = []             # 最近一次取流各接口状态，供「源自检」展示

_LABEL_KEYS = ("quality_label", "quality_desc", "label", "definition",
               "name", "quality_class", "mime", "type")
_QKEY_RE = re.compile(
    r"1080|720|480|360|4k|2160|mp4_|hd|sd|quality|definition|label", re.I)


def _looks_stream(v):
    v = (v or "").strip()
    if len(v) < 12 or v.startswith("#"):
        return False
    if not (v.startswith("http") or v.startswith("//")):
        return False
    return bool(re.search(r"\.(?:mp4|m3u8|flv|m4v|ts)(?:\?|$)", v, re.I) or
                re.search(r"weibocdn|video\.weibo|/vod/|/stream/", v, re.I))


def _json_streams(node, base, ctx="", out=None):
    """递归遍历 JSON 对象收集流地址；清晰度标签取自同层 label 字段或
    字典 key（如 urls 里的 "mp4_1080p"）。返回 (分数, 标签, URL)。"""
    if out is None:
        out = []
    if isinstance(node, dict):
        local = ctx
        for k, v in node.items():
            if isinstance(v, str) and str(k).lower() in _LABEL_KEYS and len(v) < 40:
                local = (local + " " + v).strip()
        for k, v in node.items():
            kl = str(k)
            tag = kl if _QKEY_RE.search(kl) else local
            if isinstance(v, str) and _looks_stream(v):
                a = _abs(_unescape(v.strip()), base)
                if a:
                    out.append((_qscore(tag, a, kl), tag, a))
            elif isinstance(v, (dict, list)):
                _json_streams(v, base, tag or local, out)
    elif isinstance(node, list):
        for x in node:
            _json_streams(x, base, ctx, out)
    return out


def _wb_request(url, data=None, referer="", ajax=False, timeout=6):
    """带访客 Cookie 的微博请求（GET / POST）。返回响应文本，失败返回空串。"""
    headers = {
        "User-Agent": _EXTRA_HEADERS.get("User-Agent") or WB_UA,
        "Accept": ("application/json, text/plain, */*" if ajax else
                   "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer or "https://weibo.com/",
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    if data is not None:
        headers["Origin"] = "https://weibo.com"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    ck = (_WB_USER_COOKIE or _WB_COOKIE or
          _EXTRA_HEADERS.get("Cookie") or "")
    if ck:
        headers["Cookie"] = ck
    try:
        body = data.encode("utf-8") if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, headers=headers)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=_CTX))
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "") == "gzip":
                import gzip as _gz
                try:
                    raw = _gz.decompress(raw)
                except Exception:
                    pass
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _weibo_visitor_cookie():
    """genvisitor → incarnate 换匿名访客 SUB/SUBP（等价于浏览器自动登录）。
    用户未登录也能播，靠的就是这套游客会话。"""
    global _WB_COOKIE
    if _WB_COOKIE:
        return _WB_COOKIE
    try:
        fp = urllib.parse.quote(json.dumps(
            {"os": "1", "browser": "Chrome124,0,0,0", "fonts": "undefined",
             "screenInfo": "1920*1080*24", "plugins": ""},
            separators=(",", ":")))
        b1 = _wb_request(
            "https://passport.weibo.com/visitor/genvisitor"
            "?cb=gen_callback&fp=" + fp + "&from=weibo",
            referer="https://passport.weibo.com/visitor/visitor")
        mt = re.search(r'"tid"\s*:\s*"([^"]+)"', b1 or "")
        if not mt:
            return ""
        tid = mt.group(1)
        b2 = _wb_request(
            "https://passport.weibo.com/visitor/visitor?a=incarnate&t=" +
            urllib.parse.quote(tid, safe="") +
            "&w=3&c=095&cb=restore_back&from=weibo&_rand=" +
            str(int(time.time() * 1000)),
            referer="https://passport.weibo.com/visitor/visitor")
        sub = re.search(r'"sub"\s*:\s*"([^"]+)"', b2 or "")
        subp = re.search(r'"subp"\s*:\s*"([^"]+)"', b2 or "")
        if sub:
            _WB_COOKIE = "SUB=" + sub.group(1)
            if subp:
                _WB_COOKIE += "; SUBP=" + subp.group(1)
            return _WB_COOKIE
    except Exception:
        pass
    return ""


def _weibo_mid(url):
    """返回 (数字 mid, bid)。tv/api/component 的 oid = 1034:mid。"""
    p = urllib.parse.urlsplit(url)
    bid = (p.path.rstrip("/").split("/")[-1] or "").replace(".html", "")
    m = re.search(r"1034[:/](\w{6,40})", url)
    if m:
        oid = m.group(1)
        if oid.isdigit():
            return oid, bid
        return _bid_to_mid(oid), bid
    if bid.isdigit() and len(bid) >= 10:
        return bid, bid
    return _bid_to_mid(bid), bid


def _bid_to_mid(bid):
    """微博短码(bid) -> 数字 mid，statuses/show 接口只认 mid。"""
    table = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    try:
        out = ""
        for i in range(len(bid) - 4, -4, -4):
            seg = bid[max(i, 0):i + 4]
            v = 0
            for ch in seg:
                v = v * 62 + table.index(ch)
            part = str(v)
            if i > 0:
                part = part.zfill(7)
            out = part + out
        return out
    except Exception:
        return ""


def _weibo_alt_pages(url):
    """微博页面拿不到流时的补抓入口（移动端接口常直接给 stream_url_hd）。"""
    p = urllib.parse.urlsplit(url)
    bid = (p.path.rstrip("/").split("/")[-1] or "").replace(".html", "")
    out = []
    if bid:
        mid = _bid_to_mid(bid)
        if mid:
            out.append("https://m.weibo.cn/statuses/show?id=" + mid)
            out.append("https://m.weibo.cn/detail/" + mid)
        out += ["https://m.weibo.cn/statuses/show?id=" + bid,
                "https://m.weibo.cn/detail/" + bid,
                "https://m.weibo.cn/status/" + bid]
    m = re.search(r"1034[:/](\w{6,40})", url)
    if m:
        out.append("https://weibo.com/tv/show/1034:" + m.group(1))
    return out


def _weibo_tv_api(oid, ref=""):
    """PC 视频组件接口：data.Component_Play_Playinfo.urls 是
    {"mp4_1080p":"//f.video.weibocdn.com/...","mp4_720p":"..."} 字典。
    等价于在正文页点一下播放按钮触发的那个 XHR。"""
    if not oid.startswith("1034:"):
        oid = "1034:" + oid
    try:
        page = "/tv/show/" + oid
        payload = urllib.parse.urlencode({
            "data": json.dumps({"Component_Play_Playinfo": {"oid": oid}},
                               separators=(",", ":")),
            "page": page,
        })
        return _wb_request(
            "https://weibo.com/tv/api/component?page=" +
            urllib.parse.quote(page, safe="/:"),
            data=payload,
            referer=ref or ("https://weibo.com" + page),
            ajax=True)
    except Exception:
        return ""


def _best_variant(m3u8_url, fetch=None):
    """主清单(master playlist)里挑 1080P / 最高码率那一路，返回绝对地址。"""
    fetch = fetch or _fetch
    try:
        h, final = fetch(m3u8_url, retry=0, use_cache=False)
        if not h or "#EXT-X-STREAM-INF" not in h:
            return ""
        lines = [x.strip() for x in h.splitlines() if x.strip()]
        best_url, best_sc = "", -1
        for i, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            nxt = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                if not lines[j].startswith("#"):
                    nxt = lines[j]
                    break
            if not nxt:
                continue
            sc = 0
            rm = re.search(r"RESOLUTION=(\d+)[xX](\d+)", line)
            if rm:
                sc += int(rm.group(2))
            bm = re.search(r"BANDWIDTH=(\d+)", line)
            if bm:
                sc += int(bm.group(1)) // 100000
            if "1080" in line or (rm and int(rm.group(2)) >= 1080):
                sc += 100000
            if sc > best_sc:
                best_sc, best_url = sc, _abs(nxt, final or m3u8_url)
        return best_url
    except Exception:
        return ""


# 详情页「下一级目录」的节标题特征
_EP_RE = re.compile(
    r"录像|回放|集锦|精华|第[一二三四1-4]节|加时|全场|国语|原声|"
    r"十佳球|高光|纯享|完整版", re.I)
_EP_SKIP = re.compile(
    r"统计|公众号|QQ群|淘宝|京东|优惠|电影票|小程序|关注|"
    r"上一篇|下一篇|更多|首页|末页|下一页|友情链接|免责|联系我们", re.I)
_EP_NAV = {"录像", "集锦", "新闻", "球星", "综合体育", "手机版",
           "今日视频", "昨天视频", "比赛直播", "NBA录像", "CBA录像",
           "足球录像", "综合录像"}


def _episode_group(text):
    """从 [腾讯国语] / [国语回放] 之类前缀里取分组名。"""
    m = re.match(r"^\s*[\[【(（]([^\]】)）]{1,12})[\]】)）]", text)
    if m:
        g = _text(m.group(1)).strip()
        if g and len(g) <= 12 and not re.search(r"http|www", g, re.I):
            return g
    return "录像回放"


# ======================================================================
# 分类表（动态发现为主，静态为兜底）
# ======================================================================
FALLBACK_CATS = [
    ("today", "今日视频", "/"),
    ("live", "比赛直播", "/"),
    ("nba", "NBA录像", "/nbalx/list_175_1.html"),
    ("zuqiu", "足球录像", "/football/list_208_1.html"),
    ("cba", "CBA录像", "/cba/list_180_1.html"),
    ("zonghe", "综合录像", "/zonghe/list_196_1.html"),
    ("nbajijin", "NBA集锦", "/nbajj/"),
    ("cbajijin", "CBA集锦", "/cbajj/"),
    ("zuqiujijin", "足球集锦", "/zuqiujj/"),
    ("nbaqiuxing", "篮球球星", "/shipin/lanqiuqiuxing/"),
    ("zuqiuqiuxing", "足球球星", "/shipin/zuqiuqiuxing/"),
    ("nba_lux", "NBA录像(手机版)", "/nbalx/list_175_1.html"),
    ("zuqiu_lux", "足球录像(手机版)", "/football/list_208_1.html"),
    ("cba_lux", "CBA录像(手机版)", "/cba/list_180_1.html"),
    ("zonghe_lux", "综合录像(手机版)", "/zonghe/list_196_1.html"),
    ("diag", "源自检", ""),
]

# 指定分类额外尝试的路径（真实 DedeCMS 列表在前，旧路径兜底）
CAT_PATHS = {
    "nba": ["/nbalx/list_175_1.html", "/nbalx/", "/shipin/nba/", "/nba/"],
    "zuqiu": ["/football/list_208_1.html", "/football/", "/shipin/zuqiu/", "/zuqiu/"],
    "cba": ["/cba/list_180_1.html", "/cba/", "/shipin/cba/"],
    "zonghe": ["/zonghe/list_196_1.html", "/zonghe/", "/shipin/zonghe/"],
    "nbajijin": ["/nbajj/", "/shipin/nbajijin/", "/shipin/jijin/nba/"],
    "cbajijin": ["/cbajj/", "/shipin/cbajijin/"],
    "zuqiujijin": ["/zuqiujj/", "/shipin/zuqiujijin/"],
    "nbaqiuxing": ["/shipin/lanqiuqiuxing/", "/shipin/nbaqiuxing/"],
    "zuqiuqiuxing": ["/shipin/zuqiuqiuxing/"],
    "nba_lux": ["/nbalx/list_175_1.html", "/nba/"],
    "zuqiu_lux": ["/football/list_208_1.html", "/zuqiu/"],
    "cba_lux": ["/cba/list_180_1.html", "/cba/"],
    "zonghe_lux": ["/zonghe/list_196_1.html", "/zonghe/"],
}

# 首页 / 分类页顶部导航文字 -> 归入动态分类（去重后追加）
NAV_KEYWORDS = ("录像", "集锦", "球星", "综合体育", "手机版", "今日视频",
                "昨天视频", "比赛直播", "NBA", "CBA", "足球", "篮球", "电竞")


class Spider(BaseSpider):
    VERSION = "98直播吧 OK影视 v3.0（微博游客会话+1080P）"

    def __init__(self):
        if BaseSpider is not object:
            try:
                BaseSpider.__init__(self)
            except Exception:
                pass
        self.bases = list(BASES)
        self.catmap = {k: url for k, name, url in FALLBACK_CATS}
        self.dynamic = []
        self._next_fmt = {}
        self._alt = {}
        self.inited = False
        self.force_parse = False

    # ------------------------------------------------------------------
    def getName(self):
        return "98直播吧┃[py]"

    def init(self, extend=""):
        global _WB_USER_COOKIE
        if not self.inited:
            cfg0 = {}
            if isinstance(extend, dict):
                cfg0 = extend
            elif extend:
                try:
                    cfg0 = json.loads(str(extend))
                except Exception:
                    cfg0 = {}
            wck = (cfg0.get("wb_cookie") or cfg0.get("weibo_cookie") or
                   cfg0.get("wbCookie") or cfg0.get("cookie") or "")
            if wck and "SUB" in str(wck):
                _WB_USER_COOKIE = str(wck)
        if self.inited:
            return
        self.inited = True
        cfg = {}
        if isinstance(extend, dict):
            cfg = extend
        elif extend:
            try:
                cfg = json.loads(str(extend))
            except Exception:
                cfg = {}
        b = cfg.get("base") or cfg.get("host") or cfg.get("site")
        if b:
            if not str(b).startswith("http"):
                b = "https://" + str(b)
            self.bases = [str(b).rstrip("/")] + \
                [x for x in BASES if x != str(b).rstrip("/")]
            BASES[:] = self.bases + [x for x in BASES if x not in self.bases]
        self.force_parse = bool(cfg.get("force_parse") or cfg.get("parse"))
        ck = cfg.get("cookie") or cfg.get("Cookie") or ""
        ua = cfg.get("ua") or cfg.get("UA") or ""
        if ck:
            _EXTRA_HEADERS["Cookie"] = str(ck)
        if ua:
            _EXTRA_HEADERS["User-Agent"] = str(ua)
        try:
            self._discover()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 导航自动发现
    # ------------------------------------------------------------------
    def _home(self):
        for b in self.bases[:3]:
            html, final = _fetch(b + "/", ref=None, retry=0)
            if html and len(html) > 500:
                return html, final
        return "", ""

    def _discover(self):
        html, final = self._home()
        if not html:
            return
        seen = set()
        for href, text, raw in _links(html, final):
            t = _text(text)
            if not _is_nav_text(t):
                continue
            if not any(k in t for k in NAV_KEYWORDS):
                continue
            if t in seen or href in seen:
                continue
            if re.search(r"比分直播|动画|文字直播|友情链接|联系我们|免责声明", t):
                continue
            # 导航链接通常指向栏目根路径，不带长标题
            p = urllib.parse.urlsplit(href).path.rstrip("/")
            if len(p.split("/")) > 4:
                continue
            seen.add(t)
            seen.add(href)
            # 稳定 ID：避免 Python hash 随机化导致 TVBox 缓存的分类失效
            tid = "d" + hashlib.md5((t + href).encode("utf-8")).hexdigest()[:8]
            self.dynamic.append((tid, t, href))
        # 用导航命中结果校正静态兜底路径：精确名优先，模糊名只补空缺
        exact = set()
        for tid, name, url in self.dynamic:
            key = name.replace(" ", "")
            for k, _, _ in FALLBACK_CATS:
                if k in ("today", "live", "diag"):
                    continue
                if key and key == self._cn(k):
                    self.catmap[k] = url
                    exact.add(k)
        for tid, name, url in self.dynamic:
            key = name.replace(" ", "")
            for k, _, _ in FALLBACK_CATS:
                if k in ("today", "live", "diag") or k in exact:
                    continue
                cn = self._cn(k)
                if key and cn and (key in cn or cn in key):
                    self.catmap[k] = url
                    break

    @staticmethod
    def _cn(k):
        m = {"nba": "NBA录像", "nbajijin": "NBA集锦", "nbaqiuxing": "篮球球星",
             "cba": "CBA录像", "cbajijin": "CBA集锦", "zuqiu": "足球录像",
             "zuqiujijin": "足球集锦", "zuqiuqiuxing": "足球球星",
             "zonghe": "综合录像", "nba_lux": "NBA录像", "zuqiu_lux": "足球录像",
             "cba_lux": "CBA录像", "zonghe_lux": "综合录像"}
        return m.get(k, "")

    def _cats(self):
        out = []
        used = set()
        for k, name, url in FALLBACK_CATS:
            out.append({"type_id": k, "type_name": name})
            used.add(name)
        for tid, name, url in self.dynamic[:60]:
            if name in used:
                continue
            used.add(name)
            out.append({"type_id": tid, "type_name": name})
        return out

    def _cat_url(self, tid):
        for k, name, url in FALLBACK_CATS:
            if k == tid:
                u = self.catmap.get(k) or url
                if not u:
                    return self.bases[0] + "/"
                # 相对路径：录像类列表在 98zhibo.com，门户首页在 98zb.com
                if not u.startswith("http"):
                    root = self.bases[0] + "/" if k in ("today", "live", "diag") \
                        else CAT_BASE
                    return _abs(u, root)
                return u
        for k, name, url in self.dynamic:
            if k == tid:
                return url
        return self.bases[0] + "/"

    # ------------------------------------------------------------------
    # 列表解析
    # ------------------------------------------------------------------
    def _parse_items(self, html, base):
        out, seen = [], set()
        for href, text, raw in _links(html, base):
            t = _clean_title(text)
            if not _looks_item(href, t):
                continue
            if href in seen:
                continue
            seen.add(href)
            date = ""
            m = re.search(r"((?:20)?\d{2}年)?\d{1,2}月\d{1,2}日|\d{2}年\d{2}月\d{2}日", t)
            if m:
                date = m.group(0)
            kind = "录像" if re.search(r"录像|回放|全场", t) else (
                "集锦" if re.search(r"集锦|十佳|精华", t) else "视频")
            out.append({
                "id": _enc(href),
                "name": t,
                "pic": self._pic_near(html, href),
                "remark": (date + " · " if date else "") + kind,
            })
        return out

    @staticmethod
    def _pic_near(html, href):
        try:
            pos = html.find(href)
            if pos < 0:
                pos = html.find(urllib.parse.urlsplit(href).path)
            if pos < 0:
                return ""
            seg = html[max(0, pos - 900):pos + 300]
            v = re.search(r'(?:data-original|data-src|src)\s*=\s*["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
                          seg, re.I)
            if v:
                return _abs(_unescape(v.group(1)), href)
        except Exception:
            pass
        return ""

    def _parse_schedule(self, html, base):
        """解析首页赛程块里的所有直播线路（无插件 / 插件 / 网页 / 官方源）。"""
        out, seen = [], set()
        for m in _HREF_RE.finditer(html or ""):
            raw_href = m.group(1) or m.group(2) or m.group(3) or ""
            t = _text(m.group(4))
            if not t or len(t) > 20:
                continue
            # 只收「具体线路」文字；纯导航词（比赛直播/直播/手机版）不算线路
            if not re.search(r"咪咕|CCTV|腾讯|爱奇艺|虎牙|优酷|抖音|"
                             r"无插件|插件|网页|高清|HD|直播源", t, re.I):
                continue
            if re.search(r"比分直播|动画直播|文字直播|赛程|预约", t):
                continue
            href = _abs(raw_href, base)
            if not href or href in seen:
                continue
            seen.add(href)
            ctx = _text(html[max(0, m.start() - 1200):m.end() + 500])
            tm = ""
            mt = re.search(r"\b(\d{1,2}:\d{2})\b", ctx)
            if mt:
                tm = mt.group(1)
            event = ""
            me = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,18}"
                           r"(?:杯|联赛|常规赛|季后赛|总决赛|友谊赛|资格赛|"
                           r"小组赛|决赛|半决赛|第\d+轮|大师赛|公开赛|"
                           r"俱乐部杯|冠中冠|年终总决赛))", ctx)
            if me:
                event = me.group(1)
            name = " · ".join(x for x in (event, tm, t) if x)[:60] or t
            out.append({
                "id": _enc(href),
                "name": name,
                "pic": "",
                "remark": tm or "直播线路",
            })
        return out

    def _page_url(self, cat_url, pg, html):
        if pg <= 1:
            return cat_url, html

        # ★ DedeCMS 固定格式 /nbalx/list_175_1.html —— 页码是末尾那个数字，
        #   不能用 re.search 的第一个数字（会误把栏目 ID 175 当页码）。
        dm = re.search(r"(_)(\d+)(\.html)$", cat_url, re.I)
        if dm:
            u = cat_url[:dm.start(2)] + str(pg) + cat_url[dm.end(2):]
            h, final = _fetch(u, ref=cat_url, retry=0)
            if h and self._parse_items(h, final or u):
                return u, h

        # 再从「下一页 / 末页」链接里学习分页格式：替换最后一个数字
        fmt = self._next_fmt.get(cat_url)
        if not fmt and html:
            for href, text, raw in _links(html, cat_url):
                if _text(text) in ("下一页", "下页", "末页", "»", "&raquo;"):
                    nums = list(re.finditer(r"\d+", raw or ""))
                    if nums:
                        last = nums[-1]
                        fmt = raw[:last.start()] + "{pg}" + raw[last.end():]
                        self._next_fmt[cat_url] = fmt
                        break
        cands = []
        if fmt:
            cands.append(_abs(fmt.replace("{pg}", str(pg)), cat_url))
        c = cat_url.rstrip("/")
        cands += [c + "/" + str(pg), c + "/" + str(pg) + "/",
                  c + str(pg), c + ".html?page=" + str(pg),
                  cat_url.rstrip("/") + "?page=" + str(pg)]
        for u in cands[:3]:
            if not u or u == cat_url:
                continue
            h, final = _fetch(u, ref=cat_url, retry=0)
            if h and self._parse_items(h, final or u):
                self._next_fmt[cat_url] = u.replace(str(pg), "{pg}")
                return u, h
        return cat_url, ""

    def _pagecount(self, html, pg):
        m = re.search(r"共\s*(\d+)\s*页", html or "")
        if m:
            return max(pg, int(m.group(1)))
        mx = pg
        for href, text, raw in _links(html, ""):
            for n in re.findall(r"/(\d{1,3})/?(?:\"|'|$)", raw or ""):
                try:
                    mx = max(mx, int(n))
                except Exception:
                    pass
        if re.search(r"下一页|末页", html or ""):
            mx = max(mx, pg + 1)
        return min(max(mx, pg), 9999)

    # ------------------------------------------------------------------
    # OK影视 接口：首页 / 分类 / 详情 / 搜索 / 播放
    # ------------------------------------------------------------------
    def homeContent(self, filter):
        self.init("")
        html, final = self._home()
        items = []
        if html:
            items = self._parse_items(html, final)[:24]
            live = self._parse_schedule(html, final)[:8]
            items = (live + items)[:30]
        # 首页第一条固定放「源自检」，方便真机一键看网络与解析状态
        diag_card = {"vod_id": "diag",
                     "vod_name": "⚙ 源自检 · 点我看网络与解析结果",
                     "vod_pic": "", "vod_remarks": "排障用"}
        out = {"class": self._cats(),
               "list": [diag_card] + self._vods(items)}
        if filter:
            out["filters"] = {
                "live": [{"key": "g", "name": "赛事", "value": [
                    {"n": "全部", "v": ""}, {"n": "足球", "v": "足球"},
                    {"n": "篮球", "v": "篮球"}, {"n": "NBA", "v": "NBA"},
                    {"n": "CBA", "v": "CBA"}, {"n": "电竞", "v": "电竞"},
                    {"n": "综合", "v": "综合"}]}]
            }
        return out

    def homeVideoContent(self):
        self.init("")
        html, final = self._home()
        if not html:
            return {"list": []}
        return {"list": self._vods(
            self._parse_schedule(html, final)[:6] +
            self._parse_items(html, final)[:18])}

    def categoryContent(self, tid, pg, filter, extend):
        self.init("")
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        tid = str(tid)
        ext = extend if isinstance(extend, dict) else {}

        if tid == "diag":
            return {"page": page, "pagecount": 1, "limit": 1, "total": 1,
                    "list": self._vods([
                        {"vod_id": "diag", "vod_name": "源自检 · 点开看诊断结果",
                         "vod_pic": "", "vod_remarks": "网络 / 分类 / 播放解析"}])}

        html, final = self._home()
        if tid in ("today", "live"):
            if not html:
                return self._empty(page)
            items = (self._parse_schedule(html, final) if tid == "live"
                     else self._parse_items(html, final))
            if tid == "live" and ext.get("g"):
                g = str(ext["g"])
                items = [x for x in items if g in x["name"]] or items
            return {"page": page, "pagecount": 1, "limit": max(len(items), 1),
                    "total": max(len(items), 1), "list": self._vods(items)}

        cat_url = self._cat_url(tid)
        # 首页导航若把「今日/直播」误映射成首页，仍按分类页抓
        first_html = ""
        if cat_url.rstrip("/") in (b.rstrip("/") for b in self.bases) or \
                cat_url.rstrip("/").endswith(".com"):
            cat_url = cat_url.rstrip("/") + "/"
        h1, f1 = _fetch(cat_url, ref=self.bases[0] + "/", retry=0)
        if h1:
            first_html = h1
            final = f1 or cat_url
        else:
            # 分类路径猜错时逐个候选探测（最多 4 个，单次尝试）
            tries = 0
            for p in CAT_PATHS.get(tid, []):
                for b in self.bases[:2]:
                    if tries >= 4:
                        break
                    tries += 1
                    u = b + p
                    h, f = _fetch(u, ref=b + "/", retry=0)
                    if h and self._parse_items(h, f or u):
                        cat_url, first_html, final = u, h, f or u
                        break
                if first_html:
                    break
        if not first_html:
            # 首页至少还能给出「今日视频」，不让分类空白
            if html:
                items = self._parse_items(html, final)
                return {"page": page, "pagecount": 1, "limit": len(items) or 1,
                        "total": len(items) or 1, "list": self._vods(items)}
            return self._empty(page)

        url2, h2 = self._page_url(cat_url, page, first_html)
        use_html = h2 if page > 1 else first_html
        use_base = url2 if page > 1 else (final or cat_url)
        if not use_html:
            return self._empty(page)
        items = self._parse_items(use_html, use_base)
        # 分类页若解析不到条目，回退到首页同日内容
        if not items and html:
            items = self._parse_items(html, final)
        pc = self._pagecount(first_html, page) if page == 1 else \
            max(page + (1 if re.search(r"下一页|末页", use_html) else 0), page)
        return {"page": page, "pagecount": pc, "limit": max(len(items), 20),
                "total": pc * max(len(items), 20), "list": self._vods(items)}

    @staticmethod
    def _empty(page):
        return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ------------------------------------------------------------------
    # ★ 关键：OK影视 / 影视仓 只认 vod_id / vod_name / vod_pic / vod_remarks。
    #   内部解析用的是 id/name/pic/remark，必须在返回前统一转换，否则
    #   壳拿不到 vod_id -> 卡片无标题无图(感叹号) -> 点进去「找不到数据」。
    @staticmethod
    def _safe_pic(u):
        """98 是纯文字导航站，首页多为 logo / 懒加载占位图。
        只保留明显的内容图，其余一律置空，避免坏链渲染成感叹号。"""
        u = _unescape((u or "").strip())
        if not u or not u.startswith("http") or u.startswith("data:"):
            return ""
        low = u.lower()
        if re.search(r"/(statics?|static|template|public|css|js|assets)/", low):
            return ""
        if re.search(r"(logo|loading|placeholder|blank|nopic|noimage|icon|"
                     r"sprite|lazy|avatar|banner|qrcode|ewm)", low):
            return ""
        if not re.search(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", low) and \
                not re.search(r"upload|thumb|vodpic|poster|cover", low):
            return ""
        return u

    def _vod(self, x):
        """内部条目 -> TVBox 标准 vod 条目（兼容已是标准的条目）"""
        if "vod_id" in x:
            return {
                "vod_id": x.get("vod_id", ""),
                "vod_name": _clean_title(x.get("vod_name") or x.get("name", "")),
                "vod_pic": self._safe_pic(x.get("vod_pic") or x.get("pic", "")),
                "vod_remarks": x.get("vod_remarks") or x.get("remark", ""),
            }
        return {
            "vod_id": x.get("id", ""),
            "vod_name": _clean_title(x.get("name", "")),
            "vod_pic": self._safe_pic(x.get("pic", "")),
            "vod_remarks": x.get("remark", ""),
        }

    def _vods(self, items):
        return [self._vod(x) for x in items]

    # ------------------------------------------------------------------
    def _detail_page(self, url):
        html, final = _fetch(url, ref=self.bases[0] + "/")
        if not html:
            # 换域重试一次
            sp = urllib.parse.urlsplit(url)
            for b in self.bases[1:3]:
                u = urllib.parse.urlunsplit(
                    (sp.scheme, urllib.parse.urlsplit(b).netloc,
                     sp.path, sp.query, sp.fragment))
                html, final = _fetch(u, ref=b + "/")
                if html:
                    break
        return html, final or url

    def _detail_episodes(self, html, base, page_title=""):
        """★ 解析详情页里的「下一级目录」：
        [国语回放] ... 第一节 录像 / [腾讯国语] ... 全场录像回放 / 加时赛 …
        返回 {分组名: [(集名, 播放页URL), ...]}，按页面顺序。
        """
        raw = []
        for href, text, _r in _links(html, base):
            t = _clean_title(text)
            if not t or len(t) < 8 or len(t) > 120:
                continue
            if t in _EP_NAV or not _EP_RE.search(t) or _EP_SKIP.search(t):
                continue
            if not href or href.startswith(("javascript:", "#")):
                continue
            if re.search(r"/(?:tags|tag|search|list_|plus|about|contact)/", href, re.I):
                continue
            raw.append((t, href))

        # 详情页底部有「视频录像专区」推荐其它比赛，不算本场分节。
        # 带 [xxx] 前缀的才是本场线路；一个都没有时再放宽。
        prefixed = [(t, u) for t, u in raw
                    if re.match(r"^\s*[\[【(（][^\]】)）]{1,12}[\]】)）]", t)]
        use = prefixed or raw

        groups, seen = {}, set()
        for t, href in use:
            g = _episode_group(t)
            name = t
            m = re.match(r"^\s*[\[【(（][^\]】)）]{1,12}[\]】)）]\s*(.+)$", t)
            if m:
                name = m.group(1).strip()
            short = ""
            ms = re.search(r"(第[一二三四1-4]节\s*录像|全场录像回放|全场精华回放|"
                           r"全场回放|全场集锦|加时[^ ]{0,6}|完整版|"
                           r"录像回放|精华回放)", name)
            if ms:
                short = ms.group(1)
            name = (short or name)[:40]
            key = (g, href)
            if key in seen:
                continue
            seen.add(key)
            groups.setdefault(g, [])
            if len(groups[g]) < 24:
                groups[g].append((name, href))

        # 只有单集且就是详情页自身时，不生成选集（避免自指循环）
        if len(groups) == 1:
            only = list(groups.values())[0]
            if len(only) == 1 and _same_family(only[0][1]) and \
                    only[0][1].rstrip("/") == (base or "").rstrip("/"):
                return {}
        return {k: v for k, v in groups.items() if v}

    def detailContent(self, array):
        self.init("")
        vid = str(array[0]) if isinstance(array, (list, tuple)) else str(array or "")
        if vid == "diag":
            return {"list": [{
                "vod_id": "diag", "vod_name": "源自检结果",
                "vod_pic": "", "type_name": "诊断", "vod_year": "",
                "vod_area": "", "vod_remarks": time.strftime("%Y-%m-%d %H:%M:%S"),
                "vod_actor": "", "vod_director": "",
                "vod_content": self._diag(), "vod_play_from": "98直播吧",
                "vod_play_url": "自检无需播放$" + _enc(self.bases[0] + "/"),
            }]}
        url = _dec(vid)
        if not url.startswith("http"):
            url = _abs(url, self.bases[0])
        # 防御：壳若因旧缓存传来空 vod_id，不返回空 list（否则显示「找不到数据」）
        if not url:
            return {"list": [{
                "vod_id": vid or "diag", "vod_name": "条目地址为空 · 请清缓存后重进",
                "vod_pic": "", "type_name": "诊断", "vod_year": "", "vod_area": "",
                "vod_remarks": "旧缓存", "vod_actor": "", "vod_director": "",
                "vod_content": ("上版列表字段不标准，壳缓存了没有 vod_id 的旧卡片。\n"
                                "请：替换本 py → 回首页下拉刷新（或设置里清缓存）→ 重进。\n\n"
                                + self._diag()),
                "vod_play_from": "98直播吧",
                "vod_play_url": "回到自检$" + _enc(self.bases[0] + "/"),
            }]}
        html, final = self._detail_page(url)

        title, pic, desc = url, "", ""
        if html:
            mt = re.search(r"<title[^>]*>([\s\S]{1,200}?)</title>", html, re.I)
            if mt:
                title = _clean_title(mt.group(1)) or title
            mo = re.search(r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
            if mo and len(_text(mo.group(1))) > 4:
                title = _clean_title(mo.group(1))
            mp = re.search(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
            if mp:
                pic = _abs(_unescape(mp.group(1)), final)
            if not pic:
                mi = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)', html, re.I)
                if mi:
                    pic = _abs(_unescape(mi.group(1)), final)
            md = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)
            if md:
                desc = _text(md.group(1))[:400]

        # 先尝试把本页面/iframe 里的直链找出来，能直出就不必走解析
        streams, page = [], final
        if html:
            streams, page = self._resolve_all(url, html, final)

        pic = self._safe_pic(pic)
        if not html:
            desc = ("未能抓取该页面（站点 403 / 超时 / 路径变化）。"
                    "已保留原网页解析线路，可在「源自检」查看各域连通性。\n\n"
                    + self._diag()).strip()

        # ★ 核心：98 的详情页本身就是「下一级目录」——
        #   [国语回放] 第一节 / 第二节 / 第三节 / 第四节、[腾讯国语] 全场 …
        #   每个 <a> 指向微博 / 腾讯视频等外部播放页，必须拆成选集。
        eps = self._detail_episodes(html, final, title) if html else {}
        if eps:
            froms, urlgroups = [], []
            for g, lst in eps.items():
                froms.append(g)
                urlgroups.append("#".join(
                    "%s$%s" % (nm, _enc(u)) for nm, u in lst))
            play_from = "$$$".join(froms)
            play_url = "$$$".join(urlgroups)
            n = sum(len(v) for v in eps.values())
            desc = (desc + "\n\n【本场分节】%d 个线路 / %d 集，点选集播放；"
                    "微博线路自动选 1080P，腾讯等第三方交给内置解析。"
                    % (len(eps), n)).strip()
        elif streams:
            groups = []
            for i, s in enumerate(streams[:12]):
                label = "线路%d" % (i + 1)
                if ".m3u8" in s.lower():
                    label += "·HLS"
                elif ".mp4" in s.lower():
                    label += "·MP4"
                groups.append(label + "$" + _enc(s))
            play_from, play_url = "98直连", "#".join(groups)
        else:
            # 没直链：把播放页交给播放器/OK影视 内置解析（无插件线路通常可播）
            play_from = "原网页播放"
            play_url = "打开播放页$" + _enc(page or url)
            desc = (desc + "\n\n未取到明文流地址，已交给播放器内置解析；"
                    "若仍不能播，请在「源自检」里查看链路状态。").strip()

        return {"list": [{
            "vod_id": vid, "vod_name": title, "vod_pic": pic,
            "type_name": "体育", "vod_year": "", "vod_area": "",
            "vod_remarks": "98直播吧 · 外链资源", "vod_actor": "",
            "vod_director": "", "vod_content": desc,
            "vod_play_from": play_from, "vod_play_url": play_url,
        }]}

    # ------------------------------------------------------------------
    def _resolve_all(self, origin, html, final):
        """返回 (直链列表, 最终播放页)。含 iframe 递归。"""
        found, pages = [], []
        visited = set()

        def walk(u, h, depth):
            if not h or u in visited or depth > 3:
                return
            visited.add(u)
            pages.append(u)
            ss = self._streams(h, u)
            for s in ss:
                if s not in found:
                    found.append(s)
            if found:
                return
            for f in self._frames(h, u)[:4]:
                if f in visited:
                    continue
                hh, ff = _fetch(f, ref=u, retry=0, use_cache=False)
                if hh:
                    walk(ff or f, hh, depth + 1)
                if found:
                    return

        walk(final or origin, html, 0)
        return found[:12], (pages[-1] if pages else (final or origin))

    @staticmethod
    def _streams(html, base):
        """从 HTML/JS 里挖 m3u8 / mp4 / flv 直链（含转义、参数、base64）。"""
        if not html:
            return []
        s = _unescape(html)
        if s.lstrip().startswith("#EXTM3U"):
            return [base]
        out = []

        def add(u):
            u = _unescape(u).strip().strip("'\"")
            u = u.replace("\\", "/") if u.count("\\") > 3 else u
            if not u or not _STREAM_EXT.search(u):
                return
            a = _abs(u, base)
            if a and a not in out:
                out.append(a)

        for m in _M3U8_RE.finditer(s):
            add(m.group(0))
        # "url":"xxx" / source:'xxx' / var url = "xxx"
        for m in re.finditer(
                r"""(?:["']?(?:url|playurl|play_url|video_url|m3u8|source|src|file)["']?\s*[:=]\s*|url\s*=\s*)(["'])([^"']{6,500})\1""",
                s, re.I):
            add(m.group(2))
        # url=xxx.m3u8 形式（可能在 iframe src 的 query 里）
        for m in re.finditer(r"(?:url|u|link|v)=([^\s\"'&<>]{6,500})", s, re.I):
            raw = urllib.parse.unquote(m.group(1))
            add(raw)
        # player_xxx = {...} JSON
        for m in re.finditer(r"player_[A-Za-z0-9_]*\s*=\s*(\{[\s\S]{0,4000}?\})\s*;", s):
            try:
                d = json.loads(m.group(1))
                for k in ("url", "playurl", "m3u8", "source", "video"):
                    if isinstance(d.get(k), str):
                        add(d[k])
            except Exception:
                pass
        # base64 / atob(...) 里包着地址
        for m in re.finditer(r"['\"]([A-Za-z0-9+/=]{40,1200})['\"]", s):
            try:
                d = base64.b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4))
                t = d.decode("utf-8", errors="ignore")
                if _STREAM_EXT.search(t):
                    for x in _M3U8_RE.findall(t):
                        add(x)
            except Exception:
                pass
        return out

    @staticmethod
    def _frames(html, base):
        out = []
        for m in re.finditer(
                r"""<iframe[^>]+(?:src|data-src)\s*=\s*["']([^"']+)["']""", html or "", re.I):
            u = _abs(m.group(1), base)
            if u and u not in out:
                out.append(u)
        for m in re.finditer(
                r"""(?:location\.href|window\.open|self\.location)\s*=?\s*\(?\s*["']([^"']+)["']""",
                html or "", re.I):
            u = _abs(m.group(1), base)
            if u and u not in out:
                out.append(u)
        # <a> 里明确写着「播放 / 观看 / 无插件」的外链
        for href, text, raw in _links(html, base):
            if re.search(r"点击播放|立即播放|观看|播放地址|线路", text) and \
                    len(text) < 16 and href not in out:
                out.append(href)
        return out[:8]

    # ------------------------------------------------------------------
    # 播放解析：98 中转页 → 微博 1080P / 第三方播放页 / 站点直链
    # ------------------------------------------------------------------
    def _trace_external(self, url, depth=0):
        """98 域中转页跟到真正的外链播放页（最多 2 跳）。"""
        if not _same_family(url) or depth >= 2:
            return url
        h, final = _fetch(url, ref=self.bases[0] + "/", retry=0,
                          use_cache=False)
        if not h:
            return final or url
        base = final or url
        s = _unescape(h)
        for m in re.finditer(r'https?://[^\s"\'<>\\)]+', s):
            u = m.group(0)
            if _is_play_host(u) and not _same_family(u):
                return u
        for href, text, raw in _links(h, base):
            if _is_play_host(href) and not _same_family(href):
                return href
        for fr in self._frames(h, base)[:3]:
            if fr != url:
                r = self._trace_external(fr, depth + 1)
                if r != fr:
                    return r
        return base

    def _weibo_resolve(self, url):
        """主动模拟「点播放按钮」：先建立匿名访客会话，再逐个调取流接口。
        返回 (最优流, 标签, 分数)；全过程写入 _WB_LOG 供源自检。"""
        global _WB_COOKIE
        _WB_LOG[:] = []
        mid, bid = _weibo_mid(url)
        _WB_LOG.append("bid=%s mid=%s" % (bid, mid or "转换失败"))

        # 1) 游客会话（用户填了 Cookie 就直接用，跳过这步）
        if _WB_USER_COOKIE:
            _WB_LOG.append("Cookie: 用户提供（跳过游客引导）")
        elif _WB_COOKIE:
            _WB_LOG.append("Cookie: 已缓存游客会话")
        else:
            c = _weibo_visitor_cookie()
            _WB_LOG.append("游客会话: " + ("OK (SUB/SUBP)" if c else
                           "失败 → passport.weibo.com 不可达或被风控，"
                           "请在扩展参数填 wb_cookie"))

        oid = "1034:" + mid if mid else ""
        sources = []
        if mid:
            sources += [
                ("ajax/show", "GET",
                 "https://weibo.com/ajax/statuses/show?id=" + mid +
                 "&locale=zh-CN&isGetLongText=true"),
                ("tv/component", "TV", oid),
                ("m/statuses", "GET",
                 "https://m.weibo.cn/statuses/show?id=" + mid),
                ("m/detail", "GET", "https://m.weibo.cn/detail/" + mid),
            ]
        sources.append(("pc正文页", "GET", url))
        if bid and bid != mid:
            sources.append(("m/show(bid)", "GET",
                            "https://m.weibo.cn/statuses/show?id=" + bid))

        best, sc, lab = "", 0, ""
        for name, kind, arg in sources:
            try:
                if kind == "TV":
                    body = _weibo_tv_api(arg, ref=url)
                    base = "https://weibo.com/tv/show/" + arg
                else:
                    ref = ("https://m.weibo.cn/" if "m.weibo.cn" in arg
                           else "https://weibo.com/")
                    body = _wb_request(arg, referer=ref,
                                       ajax=(name == "ajax/show"))
                    base = arg
                if not body:
                    _WB_LOG.append("%-14s 无响应(被拦/超时)" % name)
                    continue
                c = _weibo_candidates(body, base)
                _WB_LOG.append("%-14s len=%-7d 流=%-3d 最佳=%s" %
                               (name, len(body), len(c),
                                (c[0][1] or c[0][2][:46]) if c else "无"))
                if c and c[0][0] > sc:
                    best, sc, lab = c[0][2], c[0][0], c[0][1]
                if sc >= 100:
                    break
            except Exception as e:
                _WB_LOG.append("%-14s 异常 %s" % (name, str(e)[:52]))
        return best, lab, sc

    def _resolve_play_url(self, url):
        """返回 (模式, 目标, 说明)；模式 direct=可直连 / parse=交壳解析。"""
        target = self._trace_external(url) if _same_family(url) else url

        if _is_weibo(target):
            best, lab, sc = self._weibo_resolve(target)
            if best:
                if ".m3u8" in best.lower():
                    v = _best_variant(best)
                    if v:
                        best = v
                label = lab or ("1080P" if sc >= 100 else "最高可用清晰度")
                return "direct", best, "微博·" + label
            # 直链没取到：不要丢「正文页」给壳（正文页要点播放按钮，
            # 壳的嗅探打不开 → 一直转圈）。改给 tv 视频专页，它的播放器
            # 是自动加载的，壳 webview 更容易嗅探到流。
            mid, _bid = _weibo_mid(target)
            fallback = ("https://weibo.com/tv/show/1034:" + mid) if mid else target
            return "parse", fallback, ("微博直链未取到 → 交内置嗅探(tv专页)；"
                                       "建议在扩展参数填 wb_cookie 后可自动1080P")

        if _is_play_host(target):
            # 腾讯视频 / 爱奇艺等需要官方鉴权，交给 OK影视 内置解析最稳
            return "parse", target, "第三方播放页"

        h, final = _fetch(target, ref=self.bases[0] + "/", retry=0,
                          use_cache=False)
        if h:
            streams, page = self._resolve_all(target, h, final or target)
            if streams:
                best = streams[0]
                if ".m3u8" in best.lower():
                    v = _best_variant(best)
                    if v:
                        best = v
                return "direct", best, "站点直链"
            return "parse", page or target, "站点页面"
        return "parse", target, "页面不可达"

    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        self.init("")
        kw = str(key or "").strip()
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        if not kw:
            return {"list": [], "page": page}
        pool, seen = [], set()

        def collect(items):
            for x in items:
                if x["id"] in seen:
                    continue
                seen.add(x["id"])
                pool.append(x)

        # 1) 站内搜索（DedeCMS 常见路径，多个入口都试）
        q = urllib.parse.quote(kw.encode("utf-8"))
        for b in self.bases[:2]:
            for path in ("/plus/search.php?keyword=" + q,
                         "/search.php?kw=" + q,
                         "/search/?q=" + q,
                         "/so/?q=" + q):
                h, f = _fetch(b + path, ref=b + "/", retry=0)
                if h:
                    collect(self._parse_items(h, f or b + path))
                if len(pool) > 40:
                    break
            if len(pool) > 40:
                break

        # 2) 首页 + 主要分类第一页 + 近 3 天归档，本地按标题过滤
        html, final = self._home()
        if html:
            collect(self._parse_items(html, final))
            collect(self._parse_schedule(html, final))
        for tid in ("nba", "zuqiu", "cba", "zonghe"):
            if len(pool) > 120:
                break
            u = self._cat_url(tid)
            h, f = _fetch(u, ref=self.bases[0] + "/", retry=0)
            if h:
                collect(self._parse_items(h, f or u))
        for i in range(3):
            d = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
            for b in self.bases[:2]:
                h, f = _fetch(b + "/video/" + d + ".html", ref=b + "/", retry=0)
                if h:
                    collect(self._parse_items(h, f or b + "/video/" + d + ".html"))
                    break

        low = kw.lower()
        hit = [x for x in pool if low in x["name"].lower()]
        if not hit:
            chars = [c for c in low if c.strip()]
            hit = [x for x in pool
                   if chars and sum(1 for c in chars if c in x["name"].lower()) >=
                   max(1, len(chars) - 1)]
        start = (page - 1) * 30
        return {"list": self._vods(hit[start:start + 30]), "page": page,
                "pagecount": max(1, (len(hit) + 29) // 30),
                "total": len(hit)}

    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        self.init("")
        raw = str(id or "").strip()
        if "$" in raw and raw.split("$", 1)[1].startswith("u"):
            raw = raw.split("$", 1)[1].strip()
        url = _dec(raw)
        if not url.startswith("http"):
            url = _abs(url, self.bases[0])
        if not url:
            return {"parse": 0, "url": "", "playUrl": "", "msg": "地址为空"}

        if self.force_parse:
            return self._parse_mode(url)

        # 已经是明文媒体直链：若为主清单，仍自动选 1080P 那一路
        if _STREAM_EXT.search(url) or url.lstrip().startswith("#EXTM3U"):
            best = url
            if ".m3u8" in url.lower():
                v = _best_variant(url)
                if v:
                    best = v
            return self._direct(best, url)

        # 播放页（详情页选集里的 id）：跟中转 → 微博 1080P → 第三方解析
        try:
            mode, target, note = self._resolve_play_url(url)
        except Exception:
            mode, target, note = "parse", url, ""
        if mode == "direct" and target:
            r = self._direct(target, url)
            r["msg"] = note or "1080P 直连"
            return r
        r = self._parse_mode(target or url)
        if note:
            r["msg"] = note
        return r

    def _direct(self, url, ref):
        low = url.lower().split("?")[0]
        ct = ""
        if low.endswith(".m3u8"):
            ct = "application/vnd.apple.mpegurl"
        elif low.endswith(".mp4"):
            ct = "video/mp4"
        elif low.endswith(".flv"):
            ct = "video/x-flv"
        p = urllib.parse.urlsplit(ref or url)
        origin = p.scheme + "://" + p.netloc
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0,
                "header": self._play_headers(ref or url, origin),
                "contentType": ct}

    def _parse_mode(self, url):
        p = urllib.parse.urlsplit(url)
        origin = p.scheme + "://" + p.netloc
        return {"parse": 1, "playUrl": "", "url": url, "jx": 1,
                "header": self._play_headers(url, origin)}

    @staticmethod
    def _play_headers(ref="", origin=""):
        h = {"User-Agent": UA, "Accept": "*/*",
             "Accept-Language": "zh-CN,zh;q=0.9",
             "Referer": ref or BASES[0] + "/"}
        if origin:
            h["Origin"] = origin
        ck = _EXTRA_HEADERS.get("Cookie")
        if _is_weibo(ref or ""):
            ck = _WB_USER_COOKIE or _WB_COOKIE or ck
        if ck and (_same_family(ref or "") or _is_weibo(ref or "")):
            h["Cookie"] = ck
        if _EXTRA_HEADERS.get("User-Agent"):
            h["User-Agent"] = _EXTRA_HEADERS["User-Agent"]
        return h

    # ------------------------------------------------------------------
    def localProxy(self, param):
        """可选：转发 m3u8 / ts，并把 m3u8 里的相对分片补全为绝对地址。"""
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
            ref = param.get("referer", "") if isinstance(param, dict) else ""
            h, final = _fetch(url, ref=ref or None, retry=0, use_cache=False)
            if not h:
                return [502, "text/plain", b"upstream failed", {}]
            body = h
            if ".m3u8" in url.lower():
                def fix(m):
                    line = m.group(0)
                    if line.startswith(("#", "http", "//")):
                        return line
                    return _abs(line, final or url)
                body = re.sub(r"(?m)^[^\s#][^\r\n]*$", fix, h)
            ctype = "application/vnd.apple.mpegurl" if ".m3u8" in url.lower() else (
                "video/MP2T" if ".ts" in url.lower() else "application/octet-stream")
            return [200, ctype, body.encode("utf-8", errors="ignore"),
                    {"Access-Control-Allow-Origin": "*"}]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8", "ignore"), {}]

    # ------------------------------------------------------------------
    def _diag(self):
        lines = ["98直播吧 · 源自检", "时间: " + time.strftime("%Y-%m-%d %H:%M:%S"),
                 "文件版本: " + self.VERSION, ""]
        home_ok = ""
        for b in self.bases:
            h, f = _fetch(b + "/", retry=0, use_cache=False)
            cats = len([1 for _, t, _ in _links(h, f or b)
                        if _is_nav_text(t)]) if h else 0
            its = len(self._parse_items(h, f or b)) if h else 0
            lvs = len(self._parse_schedule(h, f or b)) if h else 0
            state = "OK len=%d" % len(h) if h else "不可达(403/超时)"
            lines.append("%-28s %-18s 导航%-3d 条目%-3d 线路%-3d" %
                         (b, state, cats, its, lvs))
            if h and not home_ok:
                home_ok = (h, f or b)
        lines.append("")
        lines.append("静态分类 %d 个，动态发现 %d 个" %
                     (len(FALLBACK_CATS), len(self.dynamic)))
        probe = self.homeContent(False).get("list") or []
        std = sum(1 for x in probe if x.get("vod_id") and x.get("vod_name"))
        lines.append("列表字段自检: %d/%d 条含 vod_id+vod_name %s" %
                     (std, len(probe), "OK" if std == len(probe) else "异常"))
        lines.append("附加请求头: Cookie=%s / 自定义UA=%s" %
                     ("已注入" if _EXTRA_HEADERS.get("Cookie") else "无",
                      "已注入" if _EXTRA_HEADERS.get("User-Agent") else "无"))
        lines.append("提示: 若卡片仍无标题/全是感叹号，说明旧文件未替换或壳有缓存，"
                     "请替换 py 后回首页下拉刷新 / 清缓存。")
        if not home_ok:
            lines.append("\n结论：当前网络到 98 系列域名均不可达（403/超时）。"
                         "若电脑/手机浏览器能打开，多为站点对模拟器出口的拦截。\n"
                         "可试：① 给模拟器挂与浏览器相同的代理；"
                         "② 用「一键写PY」内置浏览器打开站点后复制 Cookie，"
                         "在本源扩展参数填 {\"cookie\":\"整串Cookie\"}；"
                         "③ 换 m / www / 98zhibo 域名（已自动轮换）。")
            return "\n".join(lines)
        h, f = home_ok
        items = self._parse_items(h, f) + self._parse_schedule(h, f)
        lines.append("首页可解析条目: %d" % len(items))
        if items:
            u = _dec(items[0]["id"])
            hh, ff = _fetch(u, ref=f, retry=0, use_cache=False)
            lines.append("样本: " + items[0]["name"][:48])
            lines.append("样本页: " + u[:110])
            lines.append("样本页抓取: " + ("OK len=%d" % len(hh) if hh else "失败"))

            # ★ 下一级目录自检
            eps = self._detail_episodes(hh, ff or u) if hh else {}
            n_ep = sum(len(v) for v in eps.values())
            lines.append("分节目录: %d 组 / %d 集 %s" %
                         (len(eps), n_ep, "OK" if n_ep else "未解析到(看页面结构是否改版)"))
            if eps:
                lines.append("分组: " + " / ".join(eps.keys()))
                first_url = list(eps.values())[0][0][1]
                lines.append("首集播放页: " + first_url[:110])
                # 微博线路自动 1080P 自检
                if _is_weibo(first_url):
                    wb, lab, sc = self._weibo_resolve(first_url)
                    lines.append("--- 微博取流接口 ---")
                    for lg in _WB_LOG:
                        lines.append("  " + lg)
                    if wb:
                        lines.append("微博取流: %s → %s" %
                                     (lab or ("1080P" if sc >= 100 else "最高可用"),
                                      wb[:110]))
                        lines.append("清晰度: " + ("1080P 已自动选中" if sc >= 100
                                                  else "未找到 1080P，取最高可用"))
                    else:
                        lines.append("微博取流: 全部接口未拿到直链。")
                        lines.append("处理: 已改交「tv 视频专页」给内置嗅探，"
                                     "该页播放器自动加载，不会一直转圈。")
                        lines.append("若仍不播：在电脑浏览器打开该微博→F12→"
                                     "Network→任意 weibo.com 请求→复制整串 Cookie，"
                                     "填到本源扩展参数 {\"wb_cookie\":\"整串\"}，"
                                     "重启即可自动取 1080P 直链。")
                else:
                    lines.append("首集非微博线路，交给内置解析或站点直链嗅探。")

            streams, page = self._resolve_all(u, hh, ff or u) if hh else ([], u)
            if streams:
                lines.append("页面内联直链 %d 条，首条: %s" %
                             (len(streams), streams[0][:110]))
            if n_ep:
                lines.append("结论: 分节目录已生成，点任意一节即可播放；"
                             "微博线路自动 1080P，腾讯等第三方交内置解析。")
            else:
                lines.append("结论: 本样本页没有分节（多为直播线路或已内嵌直链页）；"
                             "请点「今日视频」里带日期的录像条目验证分节目录。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "destroy"


# 本地调试：python 98直播吧.py（不依赖 OK影视 环境）
if __name__ == "__main__":
    s = Spider()
    print(s.getName())
    print(json.dumps(s.homeContent(False), ensure_ascii=False)[:800])
