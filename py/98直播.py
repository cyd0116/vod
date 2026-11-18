"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '98直播吧',
  lang: 'hipy'
})
"""

#coding=utf-8
#!/usr/bin/python
import sys
import os
sys.path.append('..')
from base.spider import Spider
import json
import time
import base64
import re
import gzip
import zlib
import ssl
import hashlib
from urllib import request, parse
import urllib
import urllib.request
import urllib.parse

# ======================================================================
# 骨架 100% 对齐「央视节目.py」（用户实测可播放的文件）：
#   * 文件头 @header({... lang:'hipy' ...})  —— hipy 引擎靠它识别 py 源
#   * from base.spider import Spider / class Spider(Spider)
#   * 没有 __init__（基类初始化在本壳里会卡住 → 一直转圈）
#   * homeContent 纯静态；状态全部放模块级全局，不用实例属性
#   * playerContent 主链路 parse=0 直连（实测可播）；取不到直链时
#     ★ 默认兜底 = OK影视 壳子内置解析(parse=1 + jx=1)，不再丢死解析地址
#   * ★ py 不内置任何解析地址：全部从订阅 ext.parses / SUBSCRIBE_URLS 读
#     订阅 parses 仍会全量尝试，命中直链用 parse=0；没命中一律落壳子解析
#   * localProxy 返回三元素 [code, ctype, body]
# ======================================================================

# ★★ 微博分节录像若仍不能播，只改这一行 ★★
# 浏览器打开那条微博(能播就行) → F12 → Network → 点任意 weibo.com 请求
# → Headers → 复制整串 Cookie → 粘进下面两个引号之间 → 保存 → 重启 OK影视
WB_COOKIE = ""

# ======================================================================
# ★ 解析兜底配置（只在 py 自己取不到直链时才触发，不影响现有播放）
# ----------------------------------------------------------------------
# ★ 默认兜底 = OK影视 壳子内置解析（parse=1 + jx=1）
# 兜底顺序：py 直取 1080P → 订阅 parses 尝试(命中直链才用) → 壳子内置解析
#   无论「没配解析」「全部超时」「有响应但无直链」，最终默认都交壳子解析，
#   不再把死解析地址丢给播放器（转圈/感叹号），也不再停在文字提示页。
#
# 1) ★ py 里【不再内置任何解析地址】，PARSES_INLINE 默认留空 []。
#    全部解析只从订阅列表读（见下面 2），换解析改订阅即可，不用改 py。
#    PARSES_INLINE 仅作为「手动应急」入口保留，支持三种写法，可混用：
#    ① OK影视 / TVBox 原生对象写法：
#       {"name":"jx1","type":1,"url":"https://x/api/?key=xxx&url="},
#       type 字段会被忽略，py 只取 name 和 url
#    ② 纯字符串："https://jx.example.com/?url="
#    ③ 整段配置：{"parses":[{...},{...}]} 或完整的订阅 json 文本
#    ★ url 必须以 "=...url=" / "?url=" 结尾（拼原始播放页），
#      或写成含 {url} 占位的形式；不要填已经带视频地址的完整链接。
#
# 2) ★ 解析来源 = 你在 OK影视 里填的那份订阅列表（不再自动扫本机文件）
#    三种入口，可同时用，结果会合并去重：
#
#    ①【推荐·零网络最稳】在订阅 json 里给「98直播吧」这个 py 源加 ext：
#       {"key":"zb98","name":"98直播吧","type":3,
#        "api":"file://.../zb98ok.py",
#        "ext":{"parses":[
#           {"name":"jx1","type":1,"url":"http://x/api/?url="},
#           {"name":"jx2","type":1,"url":"http://y/api/?url="} ]}}
#       壳把 ext 原样传给 init(extend)，py 直接读，不需要任何联网/文件扫描。
#       ext 里也可以写整段订阅文本，或 {"subscribe":"http://订阅地址"}。
#
#    ② SUBSCRIBE_URLS：把你填进 OK影视 的订阅地址原样写这里（可多个）：
#       SUBSCRIBE_URLS = ["http://你的订阅/config.json", "https://x/tv.txt"]
#       py 在「播放兜底」时拉一次并缓存；json / txt / base64 / 行式全吃，
#       3 秒超时、只拉一层。首页/分类/自检绝不因它联网。
#
#    ③ PARSES_INLINE：默认留空（py 不再写死解析）。只在手头没有订阅
#       配置、想临时应急时才粘几条进去。
#       订阅里的 parses 项若自带 ext/header(Referer/UA/Cookie) 会一并沿用。
#    ※ PARSES_FILE 仍保留：只在你想「显式指定一个本地订阅文件」时填，
#      不会去做目录遍历扫描。
#    ★ 若三处都没给解析：兜底直接交 OK影视 壳子内置解析（parse=1），
#      或按 PARSE_DEAD_USE_SHELL 给可读文字，不会卡在死地址上。
#
# 3) ★ 自动轮流尝试「全部」解析地址：
#    PARSE_PROBE_ALL = True → 一次兜底里并行请求订阅列表中的全部解析
#      （每条 2 秒超时），一条都不漏；再按「本轮起点」的环形顺序挑第一个
#      返回有效直链的。逐条结果写进源自检。
#    PARSE_INDEX = -1 → 起点自动轮换：每次兜底换下一条打头，同一播放页
#      重试会跳过上次那条；等价于多轮把所有解析轮流试一遍。
#    PARSE_INDEX >= 0 → 锁定起点编号（探测仍会尝试全部）。
#    PARSE_PROBE = False → 不主动请求，只把轮换到的解析地址交播放器。
#
# 4) ★【默认行为】OK影视 壳子解析兜底
#    PARSE_DEAD_USE_SHELL = True（默认）：订阅解析全部超时/不可达时，
#      直接交 OK影视 壳子内置解析(parse=1 + jx=1)，不再给文字提示页。
#    SHELL_PARSE_FALLBACK = True（默认）：一条解析都没配时也交壳子解析。
#    PARSE_ADDR_FALLBACK = False（默认）：订阅解析「有响应但没吐直链」时
#      也不再把解析网页地址丢给播放器（那正是感叹号/转圈的来源），
#      一律交壳子解析。想恢复「轮换解析地址交播放器」改成 True。
#    → 把上面几个都改成 False 才回到「给可读文字提示」的老行为。
#
# 5) ★ SHELL_FIRST（默认 False）：设成 True = 纯壳模式。
#    py 取不到直链时【直接】交壳子解析，完全跳过订阅 parses 探测，
#    不花 2 秒×N 去等那些超时接口。订阅解析全不通时推荐开这个。
#    设成 False（默认）仍会先试订阅 parses，命中直链用 parse=0，
#    没命中再落壳子解析——两种都能用，默认不会转圈。
#
# 6) PARSE_URL_ENCODE：解析接口要求 urlencode 时改成 True（多数不用）。
# 7) PARSE_AS_SNIFF：默认 False = 拼好的解析地址直接交播放器(parse=0)。
#    改成 True → 解析地址也交壳嗅探(parse=1 + jx=1)。
#
# ★★ 订阅里引用本 py 的两条硬要求（否则会出现「刚装上能用、重启没分类」）★★
#    api 必须写【绝对路径】，文件名必须【纯英文】，例如：
#      "api": "/sdcard/TV/py/zb98ok.py"     （按你实际目录改）
#    不要写 "./py/98直播.py" 这类相对路径 + 中文文件名：
#    相对路径的解析基准在重启后会变，中文文件名在 URI 编码上也容易丢。
#    key 也建议纯 ASCII，如 "zb98_py"。
# ======================================================================
PARSES_INLINE = []      # ★ 不内置任何解析：全部从订阅 ext.parses / SUBSCRIBE_URLS 读
SUBSCRIBE_URLS = []
PARSES_FILE = ""
PARSE_INDEX = -1
PARSE_PROBE = True
PARSE_PROBE_ALL = True
PARSE_PROBE_TIMEOUT = 2
PARSE_PROBE_WORKERS = 6
PARSE_DEAD_USE_SHELL = True      # ★ 默认：全不可达交 OK影视 壳子解析
SHELL_FIRST = False             # True = 纯壳模式，跳过订阅 parses 探测
PARSE_ADDR_FALLBACK = False     # ★ 默认：探测没命中直链就交壳，不丢解析地址
SHELL_PARSE_FALLBACK = True      # ★ 默认：没配解析也交 OK影视 壳子解析
PARSE_URL_ENCODE = False
PARSE_AS_SNIFF = False

SITE = "https://m.98zb.com"
BASES = ["https://m.98zb.com", "https://m.98zhibo.com",
         "https://www.98zhibo.com", "https://www.98zb.com"]

# 静态分类（与站点导航一致）；第三项是导航学习失败时的兜底路径
_CATS = [
    ("today",    "今日视频", ""),
    ("live",     "直播",     ""),
    ("nba",      "NBA录像",  "/nbalx/"),
    ("zuqiu",    "足球录像", "/zqlx/"),
    ("cba",      "CBA录像",  "/cbalx/"),
    ("zonghe",   "综合录像", "/zhlx/"),
    ("nbajj",    "NBA集锦",  "/nbajj/"),
    ("zuqiujj",  "足球集锦", "/zqjj/"),
    ("cbajj",    "CBA集锦",  "/cbajj/"),
    ("nbaqx",    "篮球球星", "/nbaqx/"),
    ("zuqiuqx",  "足球球星", "/zqqx/"),
    ("nba2",     "NBA",      "/nba/"),
    ("zuqiu2",   "足球",     "/zuqiu/"),
    ("cba2",     "CBA",      "/cba/"),
    ("zonghe2",  "综合",     "/zonghe/"),
    ("mobile",   "手机版",   "/"),
    ("diag",     "源自检",   ""),
]
_CAT_NAME = dict((k, n) for k, n, _p in _CATS)

_UA = ("Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
_WB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_HREF_RE = re.compile(
    r'<a\b[^>]*?href\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([\s\S]*?)</a>', re.I)
_TAG_RE = re.compile(r'<[^>]+>')
_MEDIA_RE = re.compile(
    r'https?://[^\s"\'<>\\)]+\.(?:m3u8|mp4|flv|m4v)(?:\?[^\s"\'<>\\)]*)?', re.I)
_EP_SKIP = re.compile(
    r'统计|公众号|QQ群|淘宝|京东|优惠|电影票|小程序|上一篇|下一篇|'
    r'更多|首页|末页|下一页|友情链接|免责', re.I)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

# 模块级状态（无 __init__，避免触发基类初始化）
_G = {"home": None, "learned": False, "cat_url": {},
      "wb_visitor": "", "wb_log": [],
      "cfg_parses": [], "parses": None, "parses_note": "",
      "parse_ext": {}, "sub_urls": [], "ext_subs": [],
      "sub_parses": None, "sub_note": "", "sub_key": "",
      "parse_cursor": 0, "parse_last": {}, "parse_used": "",
      "parse_probe_log": [], "parse_round": 0, "parse_dead": False}


# ======================================================================
# 通用工具
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


def _unesc(s):
    s = str(s or "")
    for a, b in (("\\/", "/"), ("\\u002F", "/"), ("\\u003A", ":"),
                 ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def _text(s):
    return re.sub(r"\s+", " ", _unesc(_TAG_RE.sub(" ", str(s or "")))).strip()


def _abs(u, base=""):
    u = _unesc((u or "").strip())
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
        u = _abs(a or b or c or "", base)
        if u:
            out.append((u, _text(inner)))
    return out


def _enc(s):
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


def _fetch(url, ref=None, timeout=5, alt=True, extra_headers=None):
    """返回 (html, final_url)。只在用户点分类/详情/播放时调用。
    extra_headers 用于订阅 parses 里自带的 ext/header。"""
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
            hd = {"User-Agent": _UA,
                  "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                  "Accept-Language": "zh-CN,zh;q=0.9",
                  "Accept-Encoding": "gzip, deflate",
                  "Referer": ref or (SITE + "/"),
                  "Connection": "close"}
            if isinstance(extra_headers, dict):
                for _k, _v in extra_headers.items():
                    try:
                        hd[str(_k)] = str(_v)
                    except Exception:
                        pass
            req = urllib.request.Request(cu, headers=hd)
            op = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=_ctx))
            with op.open(req, timeout=timeout) as r:
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
    return re.sub(r"\s*[-_|]\s*98直播吧.*$", "", t).strip()[:90]


# ======================================================================
# 解析兜底：读取「当前播放线路的 json / txt」里的 parses 数组
#   典型 TVBox / OK影视 配置：
#   {"sites":[...], "parses":[{"name":"聚合","url":"https://jx.x.com/?url=",
#                              "type":0}, ...]}
#   ★ 纯本地文件读取，绝不发网络请求；只在需要兜底时才惰性执行。
# ======================================================================
def _candidate_files():
    """★ 不再自动扫描本机目录。只认两种显式入口：
       ① PARSES_FILE 指定的那一个订阅文件
       ② SUBSCRIBE_URLS 里用户填进 OK影视 的订阅地址（网络拉取）
    """
    out = []
    p = str(PARSES_FILE or "").strip()
    if p:
        # 兼容 file:// 前缀与 ~ 展开
        if p.startswith("file://"):
            p = p[7:]
        try:
            p = os.path.abspath(os.path.expanduser(p))
            if os.path.isfile(p):
                out.append(p)
        except Exception:
            pass
    return out


def _json_of(text):
    """纯文本 / base64 订阅 / 残缺 json 都尽力抠出 parses。"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        pad = "=" * (-len(text) % 4)
        return json.loads(base64.b64decode(text + pad).decode("utf-8", "ignore"))
    except Exception:
        pass
    # 配置被别的内容包住时，只抠 parses 数组本身
    m = re.search(r'"parses?"\s*:\s*(\[[\s\S]{0,200000}?\])', text, re.I)
    if m:
        try:
            return {"parses": json.loads(m.group(1))}
        except Exception:
            pass
    return None


def _maybe_sub_url(u):
    """判断是否是「点播订阅列表」地址（只收配置类，不收 jar/py/媒体）。"""
    if not isinstance(u, str):
        return ""
    u = u.strip()
    if not u.startswith(("http://", "https://")):
        return ""
    if re.search(r"\.(jar|py|mp4|m3u8|ts|apk|png|jpe?g)(?:\?|$)", u, re.I):
        return ""
    # 以 url= 结尾的是「解析接口」，不是订阅列表地址
    if re.search(r'[?&]url=\s*$', u, re.I):
        return ""
    if (u.lower().endswith((".json", ".txt")) or
            re.search(r"\.php|/api/|/vod|provide|subscribe|config|sub",
                      u, re.I)):
        return u
    return ""


def _collect_parses(obj, out, depth=0):
    """从配置对象里收集 (name, base_url)；顺带记录解析项自带的
    ext/header 请求头，以及配置里出现的订阅地址。"""
    if depth > 6:
        return
    if isinstance(obj, dict):
        for key in ("parses", "parse", "jx", "parser"):
            v = obj.get(key)
            if isinstance(v, (list, dict)):
                _collect_parses(v, out, depth + 1)
        # 订阅地址：urls / subscribe / spider 里的 http
        for key in ("urls", "subscribe", "sub", "spider", "api"):
            v = obj.get(key)
            if isinstance(v, str):
                su = _maybe_sub_url(v)
                if su and su not in _G["sub_urls"]:
                    _G["sub_urls"].append(su)
            elif isinstance(v, list):
                for it in v[:20]:
                    if isinstance(it, str):
                        su = _maybe_sub_url(it)
                    elif isinstance(it, dict):
                        su = _maybe_sub_url(str(it.get("url") or ""))
                    else:
                        su = ""
                    if su and su not in _G["sub_urls"]:
                        _G["sub_urls"].append(su)
        for key in ("sites", "lives"):
            arr = obj.get(key)
            if isinstance(arr, list):
                for s in arr[:40]:
                    if isinstance(s, dict) and isinstance(s.get("parses"), list):
                        _collect_parses(s["parses"], out, depth + 1)
    elif isinstance(obj, list):
        for it in obj[:120]:
            if isinstance(it, str):
                u = it.strip()
                if u.startswith("http"):
                    out.append(("解析", u))
            elif isinstance(it, dict):
                u = str(it.get("url") or it.get("api") or "").strip()
                if u.startswith("http"):
                    out.append((str(it.get("name") or "解析")[:16], u))
                    # OK影视/TVBox 的解析项常带 ext / header：
                    # {"url":"...","ext":{"Referer":"...","User-Agent":"..."}}
                    for hk in ("ext", "header", "headers"):
                        hv = it.get(hk)
                        if isinstance(hv, dict):
                            clean = {}
                            for k, v in hv.items():
                                ks = str(k)
                                if ks.startswith(("Referer", "User-Agent",
                                                  "Cookie", "Origin",
                                                  "Accept")) and v:
                                    clean[ks] = str(v)
                            if clean:
                                _G["parse_ext"][u] = clean
                if isinstance(it.get("parses"), list):
                    _collect_parses(it["parses"], out, depth + 1)


def _cfg_texts(text):
    """把订阅内容展开成多个候选文本：原文 + 一层 base64 解码。"""
    texts = [text or ""]
    try:
        t = (text or "").strip()
        if len(t) > 40:
            dec = base64.b64decode(
                t + "=" * (-len(t) % 4)).decode("utf-8", "ignore")
            if dec and dec != t:
                texts.append(dec)
    except Exception:
        pass
    return texts


def _collect_loose(text, out):
    """兜底：从纯文本/行式订阅里抠出「以 url= 结尾」的解析地址。
    兼容 名称,http://x/?url= 与 http://x/api?key=..&url= 这类写法。"""
    s = _unesc(text or "")
    for m in re.finditer(
            r'https?://[^\s"\'<>,;)\]]{6,300}?(?:\?|&)(?:[^\s"\'<>,;)\]]*&)?'
            r'url=\s*(?=[\s"\'\],;)|<]|$)', s, re.I):
        u = m.group(0).strip()
        if u not in [x[1] for x in out]:
            out.append(("订阅", u))
    # 行式："jx1,http://x/?url="
    for line in s.splitlines()[:400]:
        parts = re.split(r"[,，|\s]+", line.strip())
        for seg in parts:
            seg = seg.strip()
            if seg.startswith("http") and re.search(r'[?&]url=\s*$', seg):
                nm = parts[0][:12] if parts and parts[0] != seg else "订阅"
                if seg not in [x[1] for x in out]:
                    out.append((nm, seg))


def _collect_from_text(text, out):
    """吃下 json / txt / base64 / 被包裹 / 行式 任意一种订阅格式。"""
    got = 0
    for t in _cfg_texts(text):
        obj = _json_of(t) if ('"' in t or "{" in t or "[" in t) else None
        if obj:
            one = []
            _collect_parses(obj, one)
            for item in one:
                if item[1] not in [x[1] for x in out]:
                    out.append(item)
                    got += 1
        _collect_loose(t, out)
    return got


def _pull_subscribe(urls, found, notes, limit=8):
    """★ 直接读「你在 OK影视 里填的订阅列表」URL。
    惰性、短超时、只拉一层；按 URL 列表做缓存 key，订阅改了会自动重拉。"""
    use = [u for u in urls if u][:limit]
    key = "|".join(use)
    if _G["sub_parses"] is not None and _G["sub_key"] == key:
        for item in _G["sub_parses"]:
            if item[1] not in [x[1] for x in found]:
                found.append(item)
        if _G["sub_parses"]:
            notes.append("订阅 %d 条(缓存)" % len(_G["sub_parses"]))
        return
    pulled = []
    ok = 0
    for u in use:
        try:
            body, _f = _fetch(u, timeout=3, alt=False)
            if not body:
                continue
            one = []
            _collect_from_text(body, one)
            for item in one:
                if item[1] not in [x[1] for x in pulled]:
                    pulled.append(item)
            ok += 1
        except Exception:
            continue
    _G["sub_parses"] = pulled
    _G["sub_key"] = key
    _G["sub_note"] = "订阅 %d 个 / 成功 %d 个" % (len(use), ok)
    for item in pulled:
        if item[1] not in [x[1] for x in found]:
            found.append(item)
    if pulled:
        notes.append("订阅 %d 条" % len(pulled))


def _get_parses():
    """返回 ([(name, url)...], 说明文字)。惰性汇总一次并缓存。

    ★ py 不再内置解析；来源全部是「你在 OK影视 里填的订阅列表」：
      init(extend) 的源配置/ext.parses（零网络，主通道）→ 订阅 URL(网络)
      → PARSES_FILE（仅显式指定单个文件时读，不做目录扫描）
    另保留 PARSES_INLINE 作为手动应急入口，默认留空。
    全程只在播放兜底时执行；首页/分类/自检不因它联网。
    """
    if _G["parses"] is not None:
        return _G["parses"], _G["parses_note"]
    found = []
    notes = []
    # ★ 不清空 sub_urls / parse_ext：init(ext) 阶段已经纯内存收集过一遍，
    #   清掉会丢掉订阅里给解析项配的 ext/header 与内嵌订阅地址。

    # ① 内联（原生对象 / 字符串 / 整段配置）
    inline = PARSES_INLINE or []
    if isinstance(inline, str):
        _collect_from_text(inline, found)
    else:
        for it in list(inline):
            if isinstance(it, str):
                _collect_from_text(it, found)
            elif isinstance(it, dict):
                one = []
                _collect_parses([it], one)
                for x in one:
                    if x[1] not in [y[1] for y in found]:
                        found.append(x)
    if found:
        notes.append("内联 %d 条" % len(found))

    # ② 壳把源配置 extend 传进来
    for name, u in (_G["cfg_parses"] or []):
        if u not in [x[1] for x in found]:
            found.append((name, u))
    if _G["cfg_parses"]:
        notes.append("源配置 %d 条" % len(_G["cfg_parses"]))

    # ③ 显式指定的「单个」订阅文件（不扫描目录）
    for path in _candidate_files():
        try:
            if os.path.getsize(path) > 2048 * 1024:
                continue
            with open(path, "rb") as fp:
                txt = fp.read().decode("utf-8", "ignore")
            before = len(found)
            _collect_from_text(txt, found)
            if len(found) > before:
                notes.append("%s: +%d 条" %
                             (os.path.basename(path), len(found) - before))
        except Exception:
            continue

    # ④ 订阅 URL：py 里填的 + init(ext) 带进来的 + 配置里发现的
    subs = []
    for group in (SUBSCRIBE_URLS or [], _G["ext_subs"] or [],
                  _G["sub_urls"] or []):
        for u in group:
            if isinstance(u, str) and u.strip() and u.strip() not in subs:
                subs.append(u.strip())
    _G["sub_urls"] = subs
    if subs:
        _pull_subscribe(subs, found, notes)

    seen, uniq = set(), []
    for name, u in found:
        if u and u not in seen:
            seen.add(u)
            uniq.append((name, u))
    _G["parses"] = uniq
    _G["parses_note"] = ("；".join(notes) if notes else "未找到 parses") + \
                        "（%s）" % (_G["sub_note"] or "无订阅URL")
    return _G["parses"], _G["parses_note"]


def _parse_join(base, page):
    """把解析接口与原始播放页拼成壳可直接打开的地址。"""
    u = str(base or "").strip()
    if not u.startswith("http"):
        return ""
    tgt = (urllib.parse.quote(page, safe="") if PARSE_URL_ENCODE
           else str(page or ""))
    if "{url}" in u:
        return u.replace("{url}", tgt)
    if re.search(r'[?&](?:url|v|play|link)=$', u, re.I) or u.endswith("="):
        return u + tgt
    if "?" in u:
        return u + "&url=" + tgt
    return u + "?url=" + tgt


def _probe_extract(body):
    """从解析接口响应里抠出可直接播放的地址（JSON 字段或明文媒体串）。"""
    s = _unesc(body or "")
    for key in ("url", "playUrl", "play_url", "m3u8", "mp4", "video", "data"):
        for mm in re.finditer(r'"%s"\s*:\s*"([^"]{8,900})"' % key, s, re.I):
            u = _abs(_unesc(mm.group(1)))
            if u.startswith("http") and _MEDIA_RE.search(u):
                return u
    m = _MEDIA_RE.search(s)
    return m.group(0) if m else ""


def _probe_one(i, name, base, page):
    """请求单条解析接口，返回 (编号, 名称, 直链, 结果文字)。"""
    joined = _parse_join(base, page)
    if not joined:
        return i, name, "", "[%d]%s 地址无效" % (i, name)
    try:
        ext = (_G.get("parse_ext") or {}).get(base)
        body, _f = _fetch(joined, ref=page, timeout=PARSE_PROBE_TIMEOUT,
                          alt=False, extra_headers=ext)
    except Exception:
        body = ""
    if not body:
        return i, name, "", "[%d]%s 超时/不可达" % (i, name)
    direct = _probe_extract(body)
    if direct:
        return i, name, direct, "[%d]%s ★命中直链" % (i, name)
    return i, name, "", "[%d]%s 有响应但无直链(len=%d)" % (i, name, len(body))


def _probe_parse_all(ps, page, start):
    """★ 并行请求「全部」解析接口，一条都不漏；按配置环形顺序选第一个
    返回有效直链的。ThreadPoolExecutor 不可用时自动退回串行全量尝试。"""
    n = len(ps)
    order = [(start + k) % n for k in range(n)]
    results = []
    try:
        from concurrent.futures import ThreadPoolExecutor
        workers = 0
        try:
            workers = max(1, min(int(PARSE_PROBE_WORKERS), n))
        except Exception:
            workers = min(4, n)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_probe_one, i, ps[i][0], ps[i][1], page)
                    for i in order]
            for f in futs:
                try:
                    results.append(f.result())
                except Exception:
                    pass
    except Exception:
        results = [_probe_one(i, ps[i][0], ps[i][1], page) for i in order]

    by_i = dict((r[0], r) for r in results)
    logs = []
    for i in order:
        r = by_i.get(i)
        logs.append(r[3] if r else "[%d]%s 未执行" % (i, ps[i][0]))
    hit = -1
    direct = ""
    for i in order:                 # 按配置顺序选，不是按谁先返回
        r = by_i.get(i)
        if r and r[2]:
            hit, direct = i, r[2]
            break
    return direct, hit, logs


def _probe_parse(ps, page, start):
    """串行短路版（PARSE_PROBE_ALL=False 时用）：命中即停。"""
    n = len(ps)
    log = []
    for k in range(n):
        i = (start + k) % n
        _i, _n, direct, status = _probe_one(i, ps[i][0], ps[i][1], page)
        log.append(status)
        if direct:
            return direct, i, log
    return "", -1, log


def _parse_start(ps):
    """起点：PARSE_INDEX>=0 锁定该条；<0 时取轮换游标。"""
    try:
        fixed = int(PARSE_INDEX)
    except Exception:
        fixed = -1
    n = len(ps)
    if fixed >= 0:
        return max(0, min(fixed, n - 1)), True
    try:
        c = int(_G["parse_cursor"]) % n
    except Exception:
        c = 0
    return c, False


def _remember_parse(page, idx):
    _G["parse_last"][page] = idx
    if len(_G["parse_last"]) > 64:
        _G["parse_last"].clear()


def _fallback_parse(page, head_note, headers):
    """★ 默认兜底 = OK影视 壳子内置解析。
    链路：py直取(在外面) → 订阅 parses 全量探测(命中直链才用)
          → 没命中/全不可达/没配解析 → OK影视 壳子解析(parse=1 + jx=1)
    SHELL_FIRST=True 时跳过探测直接交壳。返回 playerContent 字典。"""
    _G["parse_used"] = ""
    _G["parse_probe_log"] = []
    # ★ 纯壳模式：不花时间等订阅解析接口，直接交 OK影视 内置解析
    if SHELL_FIRST and SHELL_PARSE_FALLBACK:
        _G["parse_dead"] = False
        _G["parse_used"] = "壳子内置解析(默认·纯壳模式)"
        return {"parse": 1, "playUrl": "", "url": page, "jx": 1,
                "header": headers, "format": "",
                "msg": (head_note + " → 默认交 OK影视 壳子内置解析。"
                        "想让 py 先试订阅 parses，把 SHELL_FIRST 改成 False。")}
    ps, note = _get_parses()
    if ps:
        n = len(ps)
        start, fixed = _parse_start(ps)
        probe_log = []

        # ① 主动尝试：默认并行请求「全部」解析，一条都不漏；
        #    再按本轮起点的环形顺序挑第一个吐直链的。
        if PARSE_PROBE:
            _G["parse_round"] = int(_G.get("parse_round") or 0) + 1
            if PARSE_PROBE_ALL:
                direct, hit, probe_log = _probe_parse_all(ps, page, start)
                how = "全部尝试 %d 条" % n
            else:
                direct, hit, probe_log = _probe_parse(ps, page, start)
                how = "逐个尝试(命中即停)"
            _G["parse_probe_log"] = probe_log
            if direct:
                _G["parse_dead"] = False
                _remember_parse(page, hit)
                _G["parse_used"] = "[%d]%s 探测直链(第%d轮)" % (
                    hit, ps[hit][0], _G["parse_round"])
                return {"parse": 0, "playUrl": "", "url": direct, "jx": 0,
                        "header": headers, "format": "video/mp4",
                        "msg": (head_note + " → %s，起点[%d]，命中 [%d/%d] %s。"
                                "逐条：%s"
                                % (how, start, hit, n, ps[hit][0],
                                   "；".join(probe_log[:8])))}

            # ①b ★ 全部解析接口都超时/不可达时，默认直接交 OK影视 壳子
            #     解析，不再把死地址丢给播放器（转圈/感叹号），也不停在文字页。
            dead = bool(probe_log) and all(
                ("超时/不可达" in x or "地址无效" in x or "未执行" in x)
                for x in probe_log)
            _G["parse_dead"] = dead
            if dead:
                _G["parse_used"] = "全部解析不可达"
                tip = (head_note + " → 订阅里的 %d 条解析接口全部超时/不可达。"
                       "若是 http://IP:端口 明文接口，Android 高版本默认"
                       "拦截明文流量，也可能接口已失效。请改用第一组"
                       "【国语回放】由 py 直取 1080P，或在订阅里换成"
                       "可用的 https 解析。已默认交 OK影视 壳子内置解析。"
                       "逐条：%s"
                       % (n, "；".join(probe_log[:8])))
                if PARSE_DEAD_USE_SHELL and SHELL_PARSE_FALLBACK:
                    return {"parse": 1, "playUrl": "", "url": page, "jx": 1,
                            "header": headers, "format": "", "msg": tip}
                return {"parse": 0, "playUrl": "",
                        "url": "【解析接口全部不可达】请改选第一组【国语回放】，"
                               "或在订阅 ext.parses 换成可用的 https 解析。",
                        "header": headers, "format": "", "msg": tip}
        else:
            _G["parse_dead"] = False

        # ② 默认不再把「有响应但没吐直链」的解析网页地址丢给播放器
        #    （那正是感叹号/转圈的来源），直接落到下面的壳子解析。
        #    只有显式开 PARSE_ADDR_FALLBACK 才恢复轮换解析地址。
        if not PARSE_ADDR_FALLBACK:
            _G["parse_used"] = "壳子内置解析(默认)"
        else:
            idx = start
            if not fixed and n > 1:
                last = _G["parse_last"].get(page)
                if last is not None and idx == last:
                    idx = (idx + 1) % n  # 同一播放页重试跳过上次那条
            name, base = ps[idx]
            joined = _parse_join(base, page)
            if joined:
                if not fixed:
                    _G["parse_cursor"] = (idx + 1) % n
                _remember_parse(page, idx)
                _G["parse_used"] = "[%d]%s 解析地址" % (idx, name)
                others = "、".join("%d:%s" % (i, nm)
                                  for i, (nm, _u) in enumerate(ps[:6]))
                sn = 1 if PARSE_AS_SNIFF else 0
                tail = ("；探测：" + "；".join(probe_log[-3:])) if probe_log else ""
                return {"parse": sn, "playUrl": "", "url": joined, "jx": sn,
                        "header": headers, "format": "",
                        "msg": (head_note + " → parses 兜底 [%d/%d] %s（自动轮换，"
                                "重试会换下一条）。候选：%s。%s"
                                % (idx, n, name, others, tail))}

    # ★ 默认兜底：OK影视 壳子内置解析
    if SHELL_PARSE_FALLBACK:
        if "默认" not in _G["parse_used"]:
            _G["parse_used"] = "壳子内置解析(默认)"
        return {"parse": 1, "playUrl": "", "url": page, "jx": 1,
                "header": headers, "format": "",
                "msg": (head_note + " → 已默认交 OK影视 壳子内置解析。"
                        "订阅 parses 没吐直链/全不可达/没配置都会走这里。"
                        "想回到文字提示，把 SHELL_PARSE_FALLBACK 改 False。")}
    return {"parse": 0, "playUrl": "", "url": ("【未取到直链】" + head_note +
            "。py 不内置解析：请在订阅里给本源加 ext.parses，"
            "或把 SHELL_PARSE_FALLBACK 改成 True。"),
            "header": headers, "format": ""}


# ======================================================================
# 微博：正文页懒加载，流地址在点播放按钮后由 JS 调接口生成。
#       py 自己建会话 + 调 ajax/statuses/show / tv/api/component 取 1080P。
# ======================================================================
_B62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _bid_to_mid(bid):
    try:
        out = ""
        for i in range(len(bid) - 4, -4, -4):
            seg = bid[max(i, 0):i + 4]
            v = 0
            for ch in seg:
                v = v * 62 + _B62.index(ch)
            out = (str(v).zfill(7) if i > 0 else str(v)) + out
        return out
    except Exception:
        return ""


def _weibo_ids(url):
    p = urllib.parse.urlsplit(url)
    bid = (p.path.rstrip("/").split("/")[-1] or "").replace(".html", "")
    m = re.search(r"1034[:/](\w{6,48})", url)
    if m:
        o = m.group(1)
        return (o if o.isdigit() else _bid_to_mid(o)), bid
    if bid.isdigit() and len(bid) >= 10:
        return bid, bid
    return _bid_to_mid(bid), bid


def _wb_req(url, data=None, ref="https://weibo.com/", ajax=False, timeout=4):
    h = {"User-Agent": _WB_UA, "Accept-Language": "zh-CN,zh;q=0.9",
         "Accept": ("application/json, text/plain, */*" if ajax
                    else "text/html,application/xhtml+xml,*/*;q=0.8"),
         "Referer": ref}
    if ajax:
        h["X-Requested-With"] = "XMLHttpRequest"
    if data is not None:
        h["Origin"] = "https://weibo.com"
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    ck = WB_COOKIE or _G["wb_visitor"]
    if ck:
        h["Cookie"] = ck
        if ajax:
            mx = re.search(r"(?:^|;\s*)XSRF-TOKEN=([^;]+)", ck)
            if mx:
                h["X-XSRF-TOKEN"] = urllib.parse.unquote(mx.group(1))
    try:
        body = data.encode("utf-8") if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, headers=h)
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=_ctx))
        with op.open(req, timeout=timeout) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


def _wb_visitor():
    if WB_COOKIE or _G["wb_visitor"]:
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
            _G["wb_visitor"] = "SUB=" + sub.group(1)
            if subp:
                _G["wb_visitor"] += "; SUBP=" + subp.group(1)
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
                out.append((_qscore(tag, kl, v), tag, _abs(_unesc(v))))
            elif isinstance(v, (dict, list)):
                _json_streams(v, tag or local, out)
    elif isinstance(node, list):
        for x in node:
            _json_streams(x, ctx, out)
    return out


def _weibo_pick(body):
    """从响应挑最高清晰度。只解析 3 个 JSON 起点，杜绝大 HTML 逐字符扫描。"""
    s = _unesc(body or "")
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
    for key in ("stream_url_hd", "mp4_hd_url", "mp4_1080p_url",
                "stream_url", "mp4_sd_url"):
        for m in re.finditer(r'"%s"\s*:\s*"([^"]{8,900})"' % key, s, re.I):
            u = _abs(_unesc(m.group(1)))
            if u:
                out.append((_qscore(key, key, u), key, u))
    for m in _MEDIA_RE.finditer(s):
        out.append((_qscore("", "", m.group(0)), "", m.group(0)))
    seen, res = set(), []
    for sc, lab, u in sorted(out, key=lambda x: -x[0]):
        if u and u not in seen:
            seen.add(u)
            res.append((sc, lab, u))
    return res


def _weibo_resolve(url):
    """返回 (最优直链, 清晰度分)。日志写 _G['wb_log'] 供源自检。"""
    log = _G["wb_log"]
    log[:] = []
    mid, bid = _weibo_ids(url)
    log.append("bid=%s mid=%s" % (bid, mid or "?"))
    if WB_COOKIE:
        log.append("Cookie: 文件顶部 WB_COOKIE 已填")
    elif _G["wb_visitor"]:
        log.append("Cookie: 已缓存游客会话")
    else:
        _wb_visitor()
        log.append("游客会话: " + ("OK" if _G["wb_visitor"]
                                  else "失败 → 请填 WB_COOKIE"))

    page = _wb_req(url, ref="https://weibo.com/", timeout=4)
    oids = []
    if page:
        for m in re.finditer(r"1034[:/]([A-Za-z0-9]{8,48})", _unesc(page)):
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
        sources.append(("ajax/mid", "GET", aj(mid), "", ""))
    if bid and bid != mid:
        sources.append(("ajax/bid", "GET", aj(bid), "", ""))
    if oids:
        oid = oids[0]
        pg = "/tv/show/" + oid
        payload = urllib.parse.urlencode({
            "data": json.dumps({"Component_Play_Playinfo": {"oid": oid}},
                               separators=(",", ":")), "page": pg})
        sources.append(("tv/component", "POST",
                        "https://weibo.com/tv/api/component?page=" +
                        urllib.parse.quote(pg, safe="/:"),
                        payload, "https://weibo.com" + pg))
    if mid:
        sources.append(("m/statuses", "GET",
                        "https://m.weibo.cn/statuses/show?id=" + mid, "", ""))
    sources.append(("pc正文页", "GET", url, "", ""))

    best, sc, auth_fail = "", 0, False
    for name, kind, arg, payload, ref in sources:
        if auth_fail and "m.weibo.cn" not in arg:
            continue
        try:
            if kind == "POST":
                body = _wb_req(arg, data=payload, ref=ref, ajax=True)
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
            c = _weibo_pick(body)
            log.append("%-13s len=%-6d 流=%d 最佳=%s" %
                       (name, len(body), len(c),
                        (c[0][1] or c[0][2][:40]) if c else "无"))
            if c and c[0][0] > sc:
                best, sc = c[0][2], c[0][0]
            if sc >= 100:
                break
        except Exception as e:
            log.append("%-13s 异常 %s" % (name, str(e)[:40]))
    if not best:
        log.append("结论: 未取到直链，请填 WB_COOKIE 后重启")
    return best, sc


# ======================================================================
# Spider —— 与「央视节目.py」逐行对齐的骨架
# ======================================================================
class Spider(Spider):

    VERSION = "98直播吧 v6.6（默认壳子解析兜底）"

    def getName(self):
        return "98直播吧"

    def init(self, extend=""):
        # ★ 直接读「订阅列表里给本源配置的 ext」：这是壳唯一保证会传给
        #   py 的通道，纯内存、零联网、零文件扫描，绝不会拖慢首页加载。
        #   支持 ext 里放：{"parses":[...]} / 整段订阅文本 /
        #   {"subscribe":"http://..."} / {"urls":["http://..."]}
        try:
            if not extend:
                return
            if isinstance(extend, dict):
                obj = extend
            else:
                s = str(extend).strip()
                try:
                    obj = json.loads(s)
                except Exception:
                    obj = s          # 整段文本交给 _collect_from_text 处理
            if isinstance(obj, str):
                one = []
                _collect_from_text(obj, one)
                if one:
                    _G["cfg_parses"] = one
            elif isinstance(obj, (dict, list)):
                one = []
                _collect_parses(obj, one)
                # ext 里若嵌了整段订阅文本("config"/"data"/"text")
                if isinstance(obj, dict):
                    for k in ("config", "data", "text", "content"):
                        v = obj.get(k)
                        if isinstance(v, str) and len(v) > 60:
                            _collect_from_text(v, one)
                # 订阅地址：subscribe / urls / sub
                if isinstance(obj, dict):
                    subs = []
                    for k in ("subscribe", "subscribeUrl", "sub", "url"):
                        u = _maybe_sub_url(str(obj.get(k) or ""))
                        if u:
                            subs.append(u)
                    arr = obj.get("urls")
                    if isinstance(arr, list):
                        for it in arr[:12]:
                            if isinstance(it, dict):
                                it = it.get("url") or ""
                            u = _maybe_sub_url(str(it or ""))
                            if u:
                                subs.append(u)
                    if subs:
                        _G["ext_subs"] = subs
                if one:
                    _G["cfg_parses"] = one
            _G["parses"] = None       # 让下次兜底重新汇总（含订阅 URL）
        except Exception:
            pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    config = {
        "player": {},
        "filter": {
            "直播": [{"key": "g", "name": "赛事", "value": [
                {"n": "全部", "v": ""}, {"n": "足球", "v": "足球"},
                {"n": "篮球", "v": "篮球"}, {"n": "NBA", "v": "NBA"},
                {"n": "CBA", "v": "CBA"}, {"n": "综合", "v": "综合"}]}]
        }
    }
    header = {
        "User-Agent": _UA,
        "Referer": SITE + "/"
    }

    # ------------------------------------------------------------------
    def homeContent(self, filter):
        """★ 纯静态、零网络 —— 与可播放样例完全一致，保证分类一定显示。"""
        result = {}
        classes = []
        for k, n, _p in _CATS:
            classes.append({'type_name': n, 'type_id': k})
        result['class'] = classes
        if filter:
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        # ★ 按用户要求：首页「更新推荐」不放诊断/提示卡片。
        #   分类由 homeContent 的 class 提供，空推荐列表不会导致分类消失。
        return {'list': []}

    # ------------------------------------------------------------------
    def _home(self):
        if _G["home"] is not None:
            return _G["home"]
        h, f = _fetch(SITE + "/", timeout=4)
        _G["home"] = (h, f)
        return _G["home"]

    def _learn(self):
        if _G["learned"]:
            return
        _G["learned"] = True
        html, final = self._home()
        if not html:
            return
        for href, text in _links(html, final):
            for k, name, _p in _CATS:
                if k in ("today", "live", "diag") or k in _G["cat_url"]:
                    continue
                if text == name or (len(text) <= len(name) + 2 and name in text):
                    _G["cat_url"][k] = href
                    break

    def _items(self, html, base):
        out, seen = [], set()
        for href, text in _links(html, base):
            t = _clean(text)
            if not t or len(t) < 9 or len(t) > 95:
                continue
            if not re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月", t):
                continue
            if not re.search(r"录像|回放|集锦|十佳|精华|全场", t):
                continue
            if _EP_SKIP.search(t) or href in seen or not _is98(href):
                continue
            seen.add(href)
            dm = re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月\d{1,2}日", t)
            out.append({"vod_id": _enc(href), "vod_name": t,
                        "vod_pic": "",
                        "vod_remarks": ((dm.group(0) + " · 录像") if dm else "录像")})
        return out

    def _live(self, html, base):
        out, seen = [], set()
        for href, text in _links(html, base):
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
        # 壳子可能以字符串传 extend，统一转 dict（照抄可播放样例）
        if not isinstance(extend, dict):
            try:
                extend = json.loads(extend) if isinstance(extend, str) and extend else {}
            except Exception:
                extend = {}
        result = {'list': [], 'page': pg, 'pagecount': 1,
                  'limit': 24, 'total': 0}
        try:
            pg = int(pg or 1)
            tid = str(tid)
            result['page'] = pg
            if tid == 'diag':
                return {'list': [{"vod_id": "diag",
                                  "vod_name": "源自检 · 点开看配置与取流日志",
                                  "vod_pic": "", "vod_remarks": "排障用"}],
                        'page': 1, 'pagecount': 1, 'limit': 1, 'total': 1}
            # ★ 订阅里分类 id 变过 / 壳用了旧缓存 tid → 一律回落今日视频
            if tid not in _CAT_NAME:
                tid = 'today'

            html, final = self._home()
            if not html:
                return {'list': [], 'page': pg, 'pagecount': 1,
                        'limit': 24, 'total': 0}
            self._learn()

            if tid == 'live':
                items = self._live(html, final)
                g = str(extend.get('g') or '')
                if g:
                    items = [x for x in items if g in x['vod_name']] or items
                result.update({'list': items, 'limit': max(len(items), 1),
                               'total': max(len(items), 1)})
                return result
            if tid == 'today':
                items = self._items(html, final)[:60]
                result.update({'list': items, 'limit': max(len(items), 1),
                               'total': max(len(items), 1)})
                return result

            url = _G["cat_url"].get(tid)
            if not url:
                for k, name, p in _CATS:
                    if k == tid and p:
                        url = _abs(p, final or SITE + "/")
                        break
            if url:
                h2, f2 = _fetch(url, ref=final or SITE + "/", timeout=5)
                if h2 and self._items(h2, f2 or url):
                    html, final = h2, (f2 or url)
            items = self._items(html, final)
            kw = _CAT_NAME.get(tid, "")
            if kw and len(items) > 8:
                key = re.sub(r"录像|集锦|球星", "", kw).strip()
                if key:
                    hit = [x for x in items if key in x['vod_name']]
                    if hit:
                        items = hit
            if pg > 1:
                for href, text in _links(html, final):
                    if _text(text) in ("下一页", "下页", "»", "末页"):
                        h3, f3 = _fetch(href, ref=final, timeout=5)
                        if h3:
                            items = self._items(h3, f3 or href)
                            result['pagecount'] = max(pg + 1, 2)
                        break
            result.update({'list': items[:60],
                           'limit': max(len(items), 24),
                           'total': max(len(items), 24)})
        except Exception:
            result['list'] = []
        return result

    # ------------------------------------------------------------------
    def _episodes(self, html, base):
        """98 详情页本身就是下一级目录：[国语回放] 第一节 … 指向外部播放页"""
        groups, seen = {}, set()
        for href, text in _links(html, base):
            t = _clean(text)
            if not t or len(t) < 9 or len(t) > 130:
                continue
            if not re.search(r'录像|回放|集锦|精华|第[一二三四1-4]节|全场', t):
                continue
            if _EP_SKIP.search(t) or not href.startswith("http"):
                continue
            m = re.match(r"^\s*[\[【(（]([^\]】)）]{1,12})[\]】)）]", t)
            if not m:
                continue
            g = m.group(1).strip()[:12]
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
        return dict((k, v) for k, v in groups.items() if v)

    def detailContent(self, array):
        vid = (str(array[0]) if isinstance(array, (list, tuple))
               else str(array)) if array else ""
        if not vid:
            return {'list': []}
        if vid in ('diag', 'hint', 'today_hint', 'err'):
            lines = ["98直播吧 · 源自检（静态·不发网络请求）",
                     "版本: " + self.VERSION, "",
                     "分类: %d 个，纯静态返回，站点不通也会显示" % len(_CATS),
                     "首页: homeContent 零网络请求 / 无 __init__", "",
                     "【微博取流配置】",
                     "WB_COOKIE: " + ("已填 ✅" if WB_COOKIE else "未填 ❌"),
                     "", "【解析来源 = 你填在 OK影视 的订阅列表】",
                     "init(ext) 订阅地址: %d 个" % len(_G["ext_subs"] or []),
                     "SUBSCRIBE_URLS: %d 个" % len(SUBSCRIBE_URLS or []),
                     "配置内发现订阅: %d 个" % len(_G["sub_urls"] or []),
                     "PARSES_FILE: " + (PARSES_FILE or "未指定(不做本地扫描)"),
                     "PARSES_INLINE: %d 条（py 已不内置，留空=只用订阅）"
                        % len(PARSES_INLINE or []),
                     "订阅拉取: " + (_G["sub_note"] or "（尚未触发）"),
                     "",
                     "PARSE_INDEX: %s（<0 为起点自动轮换）" % PARSE_INDEX,
                     "PARSE_PROBE: " + ("开" if PARSE_PROBE else "关(只交解析地址)"),
                     "PARSE_PROBE_ALL: " + ("开(并行尝试全部)" if PARSE_PROBE_ALL
                                            else "关(命中即停)"),
                     "PARSE_PROBE_TIMEOUT: %ss / 并发 %s" %
                        (PARSE_PROBE_TIMEOUT, PARSE_PROBE_WORKERS),
                     "PARSE_AS_SNIFF: " + ("开(交壳嗅探)" if PARSE_AS_SNIFF
                                            else "关(直连解析地址)"),
                     "★ 默认兜底: " + ("OK影视 壳子内置解析(parse=1+jx=1)"
                                      if SHELL_PARSE_FALLBACK else "可读文字提示"),
                     "SHELL_FIRST: " + ("开(纯壳模式·跳过订阅探测)"
                                        if SHELL_FIRST else "关(先试订阅parses)"),
                     "PARSE_DEAD_USE_SHELL: " + ("开(全不可达交壳解析)"
                                                 if PARSE_DEAD_USE_SHELL
                                                 else "关(全不可达给明确提示)"),
                     "PARSE_ADDR_FALLBACK: " + ("开(无直链时轮换解析地址)"
                                                if PARSE_ADDR_FALLBACK
                                                else "关(无直链直接交壳)"),
                     "壳子解析兜底: " + ("开启" if SHELL_PARSE_FALLBACK else "关闭"),
                     "兜底顺序: py直取 → 订阅parses全部尝试 → 壳子内置解析(默认)",
                     "上次解析可达性: " + ("全部不可达 ⚠ 已自动交壳解析"
                                        if _G["parse_dead"] else "正常/尚未触发"),
                     "本次兜底使用: " + (_G["parse_used"] or "（尚未触发）"),
                     "第 %s 轮 / 下次起点编号 %s" %
                        (_G["parse_round"], _G["parse_cursor"]),
                     ""]
            try:
                # ★ 只读「播放兜底时已缓存」的结果，绝不在这里联网拉订阅，
                #   保证诊断页 / 首页 / 分类始终是零网络，不会拖慢加载。
                _ps = _G["parses"] or []
                _note = (_G["parses_note"] or
                         "尚未触发：点一节录像让播放兜底读一次订阅即可")
                lines.append("★ 已缓存可用解析: %d 条（%s）" % (len(_ps), _note))
                for _i, (_n, _u) in enumerate(_ps[:16]):
                    lines.append("  [%d] %s → %s" % (_i, _n, _u[:76]))
                lines.append("  锁定某条：把 PARSE_INDEX 改成对应编号；"
                             "默认 -1 起点自动轮换，重试会换下一条。")
            except Exception as _e:
                lines.append("读取 parses 异常: " + str(_e)[:70])
            if _G["parse_probe_log"]:
                lines.append("上一次「全部解析尝试」逐条结果:")
                for _lg in _G["parse_probe_log"][-16:]:
                    lines.append("  " + _lg)
            lines += ["", "【上一次真实取流日志】（点一节录像后再回来）"]
            lines += ["  " + x for x in (_G["wb_log"] or ["（暂无）"])[-14:]]
            lines += ["", "【★ 重启后没分类的真因：api 写法】",
                      '"api": "./py/98直播.py"  ← 相对路径 + 中文文件名，',
                      "重启后基准目录变化 / URI 编码丢失 → 壳找不到 py。",
                      "改成绝对路径 + 纯英文文件名（key 也用 ASCII）：",
                      '  "key": "zb98_py",',
                      '  "api": "/sdcard/TV/py/zb98ok.py"   ← 按实际目录改',
                      "央视节目.py 同理：中文名改 cctv.py + 绝对路径。",
                      "", "【★ py 已不内置任何解析】",
                      "解析全部来自订阅：改订阅里的 ext.parses 即可换解析，",
                      "不用改 py。若上面显示 0 条，请检查订阅 ext 是否传入。",
                      "", "【★ 默认兜底 = OK影视 壳子内置解析】",
                      "py 直取不到 1080P 时，订阅 parses 会全部试一遍；",
                      "没吐直链 / 全超时 / 没配解析，一律交壳子解析，",
                      "不再把死解析地址丢给播放器（不会转圈/感叹号）。",
                      "订阅解析全不通时，把 SHELL_FIRST 改 True 可跳过探测，",
                      "直接交壳，起播更快。第一组【国语回放】仍由 py 直取。",
                      "", "【解析接口全部超时】",
                      "http://IP:端口 明文接口，Android 高版本默认拦截，",
                      "也可能接口已失效。换成 https 解析即可。",
                      "", "【把订阅里的 parses 喂给 py · 二选一】",
                      "A 订阅 json 里给本源加 ext.parses（零网络，最稳）",
                      "B 或在 py 顶部填 SUBSCRIBE_URLS = [\"你的订阅地址\"]",
                      "（不会自动扫本机目录，只读你指定的订阅入口）",
                      "", "清一次壳缓存 → 重新导入订阅 → 重启 OK影视"]
            return {'list': [{
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
        html, final = "", ""
        try:
            html, final = _fetch(url, ref=SITE + "/", timeout=5)
        except Exception:
            pass
        mt = re.search(r"<title[^>]*>([\s\S]{1,200}?)</title>", html or "", re.I)
        title = _clean(mt.group(1)) if mt else url

        eps = self._episodes(html, final or url) if html else {}
        if eps:
            def ratio(lst):
                return sum(1 for _n, u in lst if _is_weibo(u)) / float(len(lst) or 1)
            ordered = sorted(eps.items(), key=lambda kv: -ratio(kv[1]))
            shows, urls = [], []
            for g, lst in ordered:
                shows.append(g)
                urls.append("#".join("%s$%s" % (n, _enc(u)) for n, u in lst))
            wb_n = sum(1 for v in eps.values() for _n, u in v if _is_weibo(u))
            desc = ("【本场分节】%d 个线路 / %d 集（微博 %d 集）。第一组为微博线路，"
                    "自动选 1080P 直连；腾讯等官方页需登录鉴权，请优先用第一组。"
                    % (len(eps), sum(len(v) for v in eps.values()), wb_n))
            play_from = "$$$".join(shows)
            play_url = "$$$".join(urls)
        else:
            s = _unesc(html or "")
            streams = []
            for m in _MEDIA_RE.finditer(s):
                if m.group(0) not in streams:
                    streams.append(m.group(0))
            if streams:
                play_from = "98直连"
                play_url = "#".join("线路%d$%s" % (i + 1, _enc(u))
                                    for i, u in enumerate(streams[:8]))
            else:
                play_from = "原网页播放"
                play_url = "打开播放页$" + _enc(final or url)
            desc = "98直播吧 · 外链资源"
        return {'list': [{
            "vod_id": vid, "vod_name": title, "vod_pic": "",
            "type_name": "体育", "vod_year": "", "vod_area": "",
            "vod_remarks": "98直播吧 · 外链资源", "vod_actor": "",
            "vod_director": "", "vod_content": desc,
            "vod_play_from": play_from, "vod_play_url": play_url}]}

    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            kw = str(key or "").strip()
            if kw:
                html, final = self._home()
                videos = [x for x in self._items(html, final)
                          if kw in x['vod_name']][:40]
        except Exception:
            videos = []
        result = {'list': videos}
        return result

    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        """主链路：py 自己取 1080P 直链（parse=0，当前已实测可播）。

        ★ 仅当主链路取不到直链时才启用两层兜底：
          ① 配置 json/txt 里 "parses" 的解析接口（parse=0，拼解析地址）
          ② OK影视 壳子内置解析（parse=1 + jx=1）—— 唯一允许 parse=1 的分支
          两层都关掉时给可读文字，不再静默黑屏。
        """
        headers = {'User-Agent': _UA, 'Referer': SITE + '/'}
        target = ''
        try:
            raw = str(id or "").strip()
            target = _dec(raw)
            if not target.startswith("http"):
                target = _abs(target, SITE + "/")

            # ---- 主链路 ①：明文直链 ----
            if _stream_ok(target):
                return {"parse": 0, "playUrl": "", "url": target,
                        "jx": 0, "header": headers, "format": 'video/mp4'}

            # ---- 主链路 ②：微博主动取流（游客会话 + 接口） ----
            if _is_weibo(target):
                best, sc = _weibo_resolve(target)
                if best:
                    headers['Referer'] = 'https://weibo.com/'
                    return {"parse": 0, "playUrl": "", "url": best,
                            "jx": 0, "header": headers, "format": 'video/mp4'}
                return _fallback_parse(
                    target,
                    "微博直链未取到（" + "；".join(_G["wb_log"][-3:]) + "）",
                    self._fb_headers(target, headers))

            # ---- 主链路 ③：98 中转页 → 微博线路 / 页面内联直链 ----
            if _is98(target):
                h, f = _fetch(target, ref=SITE + "/", timeout=4)
                page = f or target
                if h:
                    for href, _t in _links(h, page):
                        if _is_weibo(href):
                            best, sc = _weibo_resolve(href)
                            if best:
                                headers['Referer'] = 'https://weibo.com/'
                                return {"parse": 0, "playUrl": "", "url": best,
                                        "jx": 0, "header": headers,
                                        "format": 'video/mp4'}
                    m = _MEDIA_RE.search(_unesc(h))
                    if m:
                        return {"parse": 0, "playUrl": "", "url": m.group(0),
                                "jx": 0, "header": headers, "format": 'video/mp4'}
                return _fallback_parse(
                    page, "98中转页未取到内联/微博直链",
                    self._fb_headers(page, headers))

            # ---- 第三方官方页：正是 parses 最擅长的场景 ----
            return _fallback_parse(
                target, "第三方官方页(腾讯/爱奇艺等)需鉴权",
                self._fb_headers(target, headers))
        except Exception as e:
            return _fallback_parse(
                target or str(id or ""),
                "播放异常 " + str(e)[:60],
                self._fb_headers(target, headers))

    @staticmethod
    def _fb_headers(page, headers):
        """兜底时把 Referer 换成原始播放页域，解析接口/壳嗅探更容易通过。"""
        try:
            p = urllib.parse.urlsplit(page)
            if p.scheme and p.netloc:
                headers = dict(headers)
                headers['Referer'] = p.scheme + "://" + p.netloc + "/"
        except Exception:
            pass
        return headers

    # ------------------------------------------------------------------
    def localProxy(self, param):
        return [200, "video/MP2T", ""]
