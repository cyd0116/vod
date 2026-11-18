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
#   * playerContent 主链路 parse=0 直连（实测可播）；仅取不到直链时
#     才按「parses 解析接口 → 壳子内置解析」两级兜底，parse=1 只出现在兜底里
#   * localProxy 返回三元素 [code, ctype, body]
# ======================================================================

# ★★ 微博分节录像若仍不能播，只改这一行 ★★
# 浏览器打开那条微博(能播就行) → F12 → Network → 点任意 weibo.com 请求
# → Headers → 复制整串 Cookie → 粘进下面两个引号之间 → 保存 → 重启 OK影视
WB_COOKIE = ""

# ======================================================================
# ★ 解析兜底配置（只在 py 自己取不到直链时才触发，不影响现有播放）
# ----------------------------------------------------------------------
# 兜底顺序：py 直取 1080P  →  parses 里的解析接口  →  OK影视壳子内置解析
#
# 1) PARSES_FILE：直接填「含 parses 的 json / txt」的绝对路径，最可靠。
#    留空则自动扫本机常见配置（TV/凯少爷.json、TV/.single_config.json、
#    tvbox 目录、py 同目录及上级的 .json/.txt）。
# 2) PARSES_INLINE：也可以把解析地址直接粘进 py，例：
#    PARSES_INLINE = ["https://jx.example.com/?url=", "https://jx2.com/play?url="]
# 3) PARSE_INDEX：自动扫到多个解析地址时用第几个（从 0 开始）。
#    源自检会列出全部候选，按里面的编号改这里即可切换。
# 4) SHELL_PARSE_FALLBACK：parses 也没有时，是否交 OK影视 内置解析
#    (parse=1, jx=1)。这是唯一允许 parse=1 的分支；若你的壳仍会转圈，
#    把它改成 False，就只会给可读文字提示。
# 5) PARSE_URL_ENCODE：解析接口要求 urlencode 时改成 True（多数不用）。
# 6) PARSE_AS_SNIFF：默认 False = 拼好的解析地址直接交播放器(parse=0)。
#    若你的壳要自己嗅探解析接口的返回，改成 True → parse=1 + jx=1。
# ======================================================================
PARSES_FILE = ""
PARSES_INLINE = [https://raw.githubusercontent.com/cyd0116/vod/refs/heads/main/mao.json]
PARSE_INDEX = 0
SHELL_PARSE_FALLBACK = True
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
      "cfg_parses": [], "parses": None, "parses_note": ""}


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


def _fetch(url, ref=None, timeout=5, alt=True):
    """返回 (html, final_url)。只在用户点分类/详情/播放时调用。"""
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
_CFG_NAMES = ("凯少爷.json", ".single_config.json", "tvbox.json",
              "TVBox.json", "config.json", "配置.json", "订阅.txt",
              "config.txt", "parses.json", "parses.txt")


def _candidate_files():
    out = []
    seen = set()

    def add(p):
        try:
            p = os.path.abspath(os.path.expanduser(str(p or "")))
            if (p and p not in seen and os.path.isfile(p)
                    and p.lower().endswith((".json", ".txt"))):
                seen.add(p)
                out.append(p)
        except Exception:
            pass

    if PARSES_FILE:
        add(PARSES_FILE)

    roots = []
    ext = str(os.environ.get("EXTERNAL_STORAGE", "") or "").strip()
    if ext:
        roots.append(ext)
    roots += ["/sdcard", "/storage/emulated/0",
              os.path.expanduser("~/storage/shared"),
              os.path.expanduser("~")]
    for root in roots:
        try:
            if not os.path.isdir(root):
                continue
            for sub in ("TV", "tvbox", "TVBox", "Download", "下载", ""):
                d = os.path.join(root, sub) if sub else root
                if not os.path.isdir(d):
                    continue
                for n in _CFG_NAMES:
                    add(os.path.join(d, n))
                try:
                    for n in sorted(os.listdir(d))[:80]:
                        if n.lower().endswith((".json", ".txt")):
                            add(os.path.join(d, n))
                except Exception:
                    pass
        except Exception:
            pass

    # py 同目录 / sys.path 里的配置（exec 加载时 __file__ 可能不存在）
    try:
        here = os.path.dirname(os.path.abspath(globals().get("__file__") or ""))
        for d in ([here, os.path.dirname(here)] if here else []) + \
                [str(x) for x in (sys.path or [])[:6]]:
            if d and os.path.isdir(d):
                for n in _CFG_NAMES:
                    add(os.path.join(d, n))
    except Exception:
        pass
    return out[:24]


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


def _collect_parses(obj, out):
    """从配置对象里收集 (name, base_url) 去重。"""
    if isinstance(obj, dict):
        for key in ("parses", "parse", "jx", "parser"):
            v = obj.get(key)
            if isinstance(v, (list, dict)):
                _collect_parses(v, out)
        for key in ("sites", "lives"):
            arr = obj.get(key)
            if not isinstance(arr, list):
                continue
            for s in arr[:40]:
                if isinstance(s, dict) and isinstance(s.get("parses"), list):
                    _collect_parses(s["parses"], out)
    elif isinstance(obj, list):
        for it in obj[:80]:
            if isinstance(it, str):
                u = it.strip()
                if u.startswith("http"):
                    out.append(("解析", u))
            elif isinstance(it, dict):
                u = str(it.get("url") or it.get("api") or "").strip()
                if u.startswith("http"):
                    out.append((str(it.get("name") or "解析")[:16], u))
                for k in ("parses", "ext"):
                    if isinstance(it.get(k), list):
                        _collect_parses(it[k], out)


def _get_parses():
    """返回 ([(name, url)...], 说明文字)。惰性读一次并缓存。"""
    if _G["parses"] is not None:
        return _G["parses"], _G["parses_note"]
    found = []
    notes = []
    for u in (PARSES_INLINE or []):
        if isinstance(u, str) and u.strip().startswith("http"):
            found.append(("内联", u.strip()))
    if found:
        notes.append("内联 %d 条" % len(found))
    for name, u in (_G["cfg_parses"] or []):
        found.append((name, u))
    if _G["cfg_parses"]:
        notes.append("源配置 %d 条" % len(_G["cfg_parses"]))

    scanned = 0
    for path in _candidate_files():
        try:
            if os.path.getsize(path) > 1536 * 1024:
                continue
            with open(path, "rb") as fp:
                raw = fp.read()
            txt = raw.decode("utf-8", "ignore")
            # 订阅 txt 常是整段 base64，原文里没有 "parse" 字样，
            # 先解一层再判断，否则会被预检查误跳过。
            texts = [txt]
            try:
                t = txt.strip()
                dec = base64.b64decode(
                    t + "=" * (-len(t) % 4)).decode("utf-8", "ignore")
                if dec and dec != txt:
                    texts.append(dec)
            except Exception:
                pass
            obj = None
            for t in texts:
                if '"parse' in t.lower():
                    obj = _json_of(t)
                    if obj:
                        break
            if not obj:
                continue
            one = []
            _collect_parses(obj, one)
            for name, u in one:
                if (name, u) not in found:
                    found.append((name, u))
            scanned += 1
            if one:
                notes.append("%s: %d 条" % (os.path.basename(path), len(one)))
        except Exception:
            continue

    seen, uniq = set(), []
    for name, u in found:
        if u not in seen:
            seen.add(u)
            uniq.append((name, u))
    _G["parses"] = uniq
    _G["parses_note"] = ("；".join(notes) if notes else "未找到 parses") + \
                        "（扫描 %d 个配置）" % scanned
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


def _fallback_parse(page, head_note, headers):
    """兜底链：parses 解析接口 → OK影视壳子内置解析 → 可读文字。
    返回 playerContent 字典（绝不返回 None）。"""
    ps, note = _get_parses()
    if ps:
        idx = 0
        try:
            idx = max(0, min(int(PARSE_INDEX), len(ps) - 1))
        except Exception:
            pass
        name, base = ps[idx]
        joined = _parse_join(base, page)
        if joined:
            others = "、".join("%d:%s" % (i, n) for i, (n, _u) in enumerate(ps[:6]))
            sn = 1 if PARSE_AS_SNIFF else 0
            return {"parse": sn, "playUrl": "", "url": joined, "jx": sn,
                    "header": headers, "format": "",
                    "msg": (head_note + " → 已用 parses 兜底 [%d/%d] %s。"
                            "候选：%s。换解析请改本 py 顶部 PARSE_INDEX；"
                            "若解析接口不生效可把 PARSE_AS_SNIFF 改成 True。"
                            % (idx, len(ps), name, others))}
    if SHELL_PARSE_FALLBACK:
        return {"parse": 1, "playUrl": "", "url": page, "jx": 1,
                "header": headers, "format": "",
                "msg": (head_note + " → 已交 OK影视 内置解析兜底（parses 未命中）。"
                        "若又一直转圈，把本 py 顶部 SHELL_PARSE_FALLBACK 改成 False。")}
    return {"parse": 0, "playUrl": "", "url": ("【未取到直链】" + head_note +
            "。可在本 py 顶部 PARSES_INLINE / PARSES_FILE 填解析地址，"
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

    VERSION = "98直播吧 v6.1（parses+壳解析双兜底）"

    def getName(self):
        return "98直播吧"

    def init(self, extend=""):
        # 壳若把源配置（含 parses）传进来就直接采用；纯内存解析，
        # 不抓网、不读文件，绝不会拖慢首页加载。
        try:
            if extend:
                obj = extend if isinstance(extend, dict) else json.loads(str(extend))
                if isinstance(obj, dict) or isinstance(obj, list):
                    one = []
                    _collect_parses(obj, one)
                    if one:
                        _G["cfg_parses"] = one
                        _G["parses"] = None   # 让下次兜底重新汇总
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
        result = {'list': []}
        return result

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

            html, final = self._home()
            if not html:
                return result
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
        except Exception as e:
            result['list'] = [{"vod_id": "err",
                               "vod_name": "分类加载异常",
                               "vod_pic": "", "vod_remarks": str(e)[:60]}]
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
        if vid == 'diag':
            lines = ["98直播吧 · 源自检（静态·不发网络请求）",
                     "版本: " + self.VERSION, "",
                     "分类: %d 个，纯静态返回，站点不通也会显示" % len(_CATS),
                     "首页: homeContent 零网络请求 / 无 __init__", "",
                     "【微博取流配置】",
                     "WB_COOKIE: " + ("已填 ✅" if WB_COOKIE else "未填 ❌"),
                     "", "【解析兜底配置】",
                     "PARSES_FILE: " + (PARSES_FILE or "未指定(自动扫描)"),
                     "PARSES_INLINE: %d 条" % len(PARSES_INLINE or []),
                     "PARSE_INDEX: %s" % PARSE_INDEX,
                     "PARSE_AS_SNIFF: " + ("开(交壳嗅探)" if PARSE_AS_SNIFF
                                            else "关(直连解析地址)"),
                     "壳子解析兜底: " + ("开启" if SHELL_PARSE_FALLBACK else "关闭"),
                     "兜底顺序: py直取 → parses解析接口 → 壳子内置解析",
                     ""]
            try:
                _ps, _note = _get_parses()
                lines.append("读取结果: %d 条可用解析（%s）" % (len(_ps), _note))
                for _i, (_n, _u) in enumerate(_ps[:8]):
                    lines.append("  [%d] %s → %s" % (_i, _n, _u[:78]))
                lines.append("  换解析：把本 py 顶部 PARSE_INDEX 改成对应编号。")
            except Exception as _e:
                lines.append("读取 parses 异常: " + str(_e)[:70])
            lines += ["", "【上一次真实取流日志】（点一节录像后再回来）"]
            lines += ["  " + x for x in (_G["wb_log"] or ["（暂无）"])[-14:]]
            lines += ["", "【若仍不能播 · 只改一行】",
                      "浏览器打开那条微博 → F12 → Network → 点任意 weibo.com 请求",
                      "→ Headers 复制整串 Cookie → 粘进本 py 顶部 WB_COOKIE = \"\"",
                      "→ 保存 → 删除源重新添加 → 重启 OK影视。"]
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
