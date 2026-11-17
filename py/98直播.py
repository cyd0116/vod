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
    "https://m.98zb.com",
    "https://www.98zb.com",
    "https://m.98zhibo.com",
    "https://www.98zhibo.com",
]
UA = ("Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
TIMEOUT = 8
CACHE_TTL = 90
_CACHE = {}

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
# 分类表（动态发现为主，静态为兜底）
# ======================================================================
FALLBACK_CATS = [
    ("today", "今日视频", "/"),
    ("live", "比赛直播", "/"),
    ("nba", "NBA录像", "/shipin/nba/"),
    ("nbajijin", "NBA集锦", "/shipin/nbajijin/"),
    ("nbaqiuxing", "篮球球星", "/shipin/lanqiuqiuxing/"),
    ("cba", "CBA录像", "/shipin/cba/"),
    ("cbajijin", "CBA集锦", "/shipin/cbajijin/"),
    ("zuqiu", "足球录像", "/shipin/zuqiu/"),
    ("zuqiujijin", "足球集锦", "/shipin/zuqiujijin/"),
    ("zuqiuqiuxing", "足球球星", "/shipin/zuqiuqiuxing/"),
    ("zonghe", "综合体育", "/shipin/zonghe/"),
    ("nba_lux", "NBA录像(手机版)", "/nba/"),
    ("zuqiu_lux", "足球录像(手机版)", "/zuqiu/"),
    ("cba_lux", "CBA录像(手机版)", "/cba/"),
    ("zonghe_lux", "综合录像(手机版)", "/zonghe/"),
    ("diag", "源自检", ""),
]

# 指定分类额外尝试的路径（站点分类拼音不固定，逐个探测）
CAT_PATHS = {
    "nba": ["/shipin/nba/", "/shipin/nbaluxiang/", "/nba/", "/nbaluxiang/"],
    "cba": ["/shipin/cba/", "/shipin/cbaluxiang/", "/cba/", "/cbaluxiang/"],
    "zuqiu": ["/shipin/zuqiu/", "/shipin/zuqiuluxiang/", "/zuqiu/", "/zuqiuluxiang/"],
    "zonghe": ["/shipin/zonghe/", "/shipin/qita/", "/shipin/zonghetiyu/", "/zonghe/"],
    "nbajijin": ["/shipin/nbajijin/", "/shipin/jijin/nba/"],
    "cbajijin": ["/shipin/cbajijin/"],
    "zuqiujijin": ["/shipin/zuqiujijin/"],
    "nbaqiuxing": ["/shipin/lanqiuqiuxing/", "/shipin/nbaqiuxing/"],
    "zuqiuqiuxing": ["/shipin/zuqiuqiuxing/"],
    "nba_lux": ["/nba/", "/shipin/nba/"],
    "zuqiu_lux": ["/zuqiu/", "/shipin/zuqiu/"],
    "cba_lux": ["/cba/", "/shipin/cba/"],
    "zonghe_lux": ["/zonghe/", "/shipin/zonghe/"],
}

# 首页 / 分类页顶部导航文字 -> 归入动态分类（去重后追加）
NAV_KEYWORDS = ("录像", "集锦", "球星", "综合体育", "手机版", "今日视频",
                "昨天视频", "比赛直播", "NBA", "CBA", "足球", "篮球", "电竞")


class Spider(BaseSpider):
    VERSION = "98直播吧 OK影视 v1.0"

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
             "zonghe": "综合体育", "nba_lux": "NBA录像", "zuqiu_lux": "足球录像",
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
                return _abs(u, self.bases[0]) if u else self.bases[0] + "/"
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
            if not re.search(r"直播|无插件|插件|网页", t):
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
        # 先从「下一页 / 末页」链接里学习分页格式
        fmt = self._next_fmt.get(cat_url)
        if not fmt and html:
            for href, text, raw in _links(html, cat_url):
                if _text(text) in ("下一页", "下页", "末页", "»", "&raquo;"):
                    m = re.search(r"(\d+)", raw)
                    if m:
                        fmt = raw.replace(m.group(1), "{pg}")
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
        out = {"class": self._cats(), "list": items}
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
        return {"list": (self._parse_schedule(html, final)[:6] +
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
                    "list": [{"vod_id": "diag", "vod_name": "源自检 · 点开看诊断结果",
                              "vod_pic": "", "vod_remarks": "网络 / 分类 / 播放解析"}]}

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
                    "total": max(len(items), 1), "list": items}

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
                        "total": len(items) or 1, "list": items}
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
                "total": pc * max(len(items), 20), "list": items}

    @staticmethod
    def _empty(page):
        return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

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

        if streams:
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
        return {"list": hit[start:start + 30], "page": page,
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

        candidates = [url] + list(self._alt.get(url, []))[:3]
        if self.force_parse:
            return self._parse_mode(candidates[0])
        for u in candidates:
            # 直链直接播
            if _STREAM_EXT.search(u) or u.lstrip().startswith("#EXTM3U"):
                return self._direct(u, u)
            h, final = _fetch(u, ref=self.bases[0] + "/", retry=0,
                              use_cache=False)
            if not h:
                continue
            streams, page = self._resolve_all(u, h, final or u)
            if streams:
                return self._direct(streams[0], final or u)
            # iframe 页没明文流：把最内层播放页交给内置解析
            return self._parse_mode(page or u)
        return self._parse_mode(candidates[0])

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
        if not home_ok:
            lines.append("\n结论：当前网络到 98 系列域名均不可达。"
                         "请在手机/电视同网络下打开本源；若手机浏览器能打开"
                         "而这里不可达，多为站点对数据中心 IP 的拦截。")
            return "\n".join(lines)
        h, f = home_ok
        items = self._parse_items(h, f) + self._parse_schedule(h, f)
        lines.append("首页可解析条目: %d" % len(items))
        if items:
            u = _dec(items[0]["id"])
            hh, ff = _fetch(u, ref=f, retry=0, use_cache=False)
            streams, page = self._resolve_all(u, hh, ff or u)
            lines.append("样本: " + items[0]["name"][:48])
            lines.append("样本页: " + u[:110])
            lines.append("样本页抓取: " + ("OK len=%d" % len(hh) if hh else "失败"))
            if streams:
                lines.append("解析到直链 %d 条，首条: %s" %
                             (len(streams), streams[0][:110]))
                lines.append("结论: 直连模式(parse=0)，可直接播放。")
            else:
                lines.append("未取到明文流地址，最终播放页: " + (page or u)[:110])
                lines.append("结论: 走内置解析(parse=1)；若电视端仍黑屏，"
                             "在 init 里传 {\"force_parse\":false} 或换解码器。")
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
