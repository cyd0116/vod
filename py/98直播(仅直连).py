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
import threading
from datetime import date, timedelta

# ======================================================================
# 骨架 100% 对齐「央视节目.py」（用户实测可播放的文件）：
#   * 文件头 @header({... lang:'hipy' ...})  —— hipy 引擎靠它识别 py 源
#   * from base.spider import Spider / class Spider(Spider)
#   * 没有 __init__（基类初始化在本壳里会卡住 → 一直转圈）
#   * homeContent 纯静态；状态全部放模块级全局，不用实例属性
#   * playerContent 主链路 parse=0 直连（实测可播）；取不到直链时
#     ★ 默认兜底 = OK影视 壳子内置解析(parse=1 + jx=1)，不丢解析网页地址
#   * ★ py 不内置任何解析地址：全部从订阅 ext.parses / SUBSCRIBE_URLS 读
#     订阅 parses 仍会全量尝试，命中直链用 parse=0；没命中一律落壳子解析
#   * ★★ 官方视频(腾讯国语/腾讯原声等) v7.5：还原真实官方页再交壳。
#     98 详情页给腾讯线路常是【本站中转页】，真实页藏在 iframe/JS/?url=
#     里；只抓 <a href> 会把 98 中转页交给壳 → 壳不认域名 → 全部
#     「播放地址解析失败」。现在从整页(含 query/302/iframe/JS)抠出
#     v.qq.com 等真实官方页，再极简交壳，顺序仍由壳(超级解析→https)。
#     不试直连/不取流/不探测/不重试/不写 msg；自检可回显完整链路。
#     备选 OFFICIAL_SNIFF_PREFIX="video://" 走 X5 WebView 嗅探。
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
#   不再把解析网页地址丢给播放器（转圈/感叹号），也不再停在文字提示页。
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
#    ③ PARSES_INLINE：默认留空（py 不内置解析）。只在手头没有订阅
#       配置、想临时应急时才粘几条进去。
#       订阅里的 parses 项若自带 ext/header(Referer/UA/Cookie) 会一并沿用。
#    ※ PARSES_FILE 仍保留：只在你想「显式指定一个本地订阅文件」时填，
#      不会去做目录遍历扫描。
#    ★ 若三处都没给解析：兜底直接交 OK影视 壳子内置解析（parse=1），
#      或按 PARSE_DEAD_USE_SHELL 给可读文字，不会卡在解析网页上。
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
# 4) ★★【默认顺序】★★
#      ⓪ 官方页(腾讯/爱奇艺/优酷/咪咕)：最高优先级直通壳解析，
#         零探测、零提示、带 flag；实测 98 点进去自动播放且壳能解析。
#      ① py 直取 1080P 直链（playerContent 主链路，没变）
#      ② 取不到 → 【一律先交 OK影视 壳子自带解析】(parse=1 + jx=1)
#      ③ 壳解析播不了、返回再点同一集 → 订阅 ext.parses 全量并行尝试，
#         命中直链用 parse=0；没命中/全超时又回 ②（壳 → parses → 壳 循环）
#      ※ ⓪ 不参与 ②③ 的重试循环，因为壳解析对它已有效。
#
#    ⚠ 技术边界（必须知道）：playerContent 是一次性返回，parse=1 一旦交
#      给壳，py 这一轮就结束了，没有「壳失败再回调 py」的机制。所以
#      「先壳再 parses」在同一次点击里做不到，只能落在「重试」上实现：
#      第 1 次点 = 壳自带解析；播不了退出来再点该集 = 订阅 parses 全量。
#      这正是上面 ②③ 的用户可感知顺序，也是唯一能真正成立的实现。
#
#    SHELL_FIRST = True（默认）：开启「先壳」。
#    PARSE_ON_RETRY = True（默认）：重试时才跑订阅 parses 全量尝试。
#      两者都开 = 上面 ①②③。把 SHELL_FIRST 改 False 会回到老顺序
#      （先 parses 后壳）；把 PARSE_ON_RETRY 改 False = 永远只用壳。
#
# 5) 其余开关（只在 SHELL_FIRST=False 的老链路里生效）：
#    PARSE_DEAD_USE_SHELL = True：parses 全不可达时交壳，不给文字页。
#    SHELL_PARSE_FALLBACK = True：一条解析都没配也交壳。
#    PARSE_ADDR_FALLBACK = False：不把解析网页地址丢给播放器（转圈来源）。
#      想恢复「轮换解析地址交播放器」改成 True。
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
PARSE_DEAD_USE_SHELL = True      # 老链路用：全不可达交壳
SHELL_FIRST = True               # ★★ 默认：直取失败一律先交 OK影视 壳子自带解析
PARSE_ON_RETRY = True           # ★★ 默认：同一集重试时才试订阅 ext.parses 全量
PARSE_ADDR_FALLBACK = False     # 默认：不丢解析网页地址给播放器
SHELL_PARSE_FALLBACK = True      # ★ 默认：壳子解析总兜底开启
PARSE_URL_ENCODE = False
PARSE_AS_SNIFF = False

# ======================================================================
# ★★ 官方页（腾讯/爱奇艺/优酷/咪咕）：py 完全不碰，原样交壳解析
#   官方视频不能直连；壳本身已配好「超级解析 → 失败自动走 https 解析」。
#   playerContent 识别到官方页就【最早短路】：不试直连、不取流、
#   不探测订阅 parses、不带任何提示；v7.5 会先把中转页还原成真实官方页。
#   98 中转页里若嵌官方页，会先抽出真实官方页再交，不丢中转页给壳。
#
#   B 备选：OFFICIAL_SNIFF_PREFIX="video://" → 改 parse=0 交 video:// 网页，
#     让 X5 WebView 渲染嗅探（需电视端 + X5 内核）。默认留空不用。
# ======================================================================
OFFICIAL_SNIFF_PREFIX = ""   # 留空 = 走壳解析池；填 "video://" 走 B
OFFICIAL_PAGE_HINT = False
OFFICIAL_ADD_FLAG = True     # 回传 flag=qq/iqiyi…，帮壳匹配解析项 ext.flag
# ★★ jx=1 = 让壳真正【调用解析池】的开关。关掉时 parse=1 只走壳自带
#    WebView 嗅探网页 → 抓到官网贴片广告、底部不会出现解析名字。
#    与 msg 无关：msg 才是 ⚠ 错误页的元凶，永远不补。
OFFICIAL_JX = True

# ======================================================================
# ★★ v7.5 官方视频（腾讯国语/腾讯原声等）：还原真实官方页后交壳
#
#   实测确认：官方页不能直连，也不需要 py 先试直连/先试解析。
#   壳本身已配好顺序 —— 先【超级解析】，失败后自动走【https 解析】。
#   这是壳内部的解析链，不需要回调 py。所以 py 只做一件事：
#     识别到官方页 → 原样极简交壳(parse=1 + url + header，零 msg)
#   不探测、不取流、不拼解析地址、不重试、不带 flag/format/playUrl。
#
#   ★ 交壳必须零 msg：壳会把 playerContent.msg 当「播放失败原因」
#     弹 ⚠ 页并中断解析（就是早先截图那行字的来源）。
#   ★ 官方页判定放在 playerContent 最前，连 _stream_ok 都不经过，
#     确保「直接走壳子超级解析」，不做任何直连尝试。
#
#   下面两个开关只作兼容保留，默认全关；打开会让 py 抢在壳前面，
#   与「先超级解析、后 https」的顺序冲突，不建议。
# ======================================================================
OFFICIAL_CLEAN = True          # ★ 交壳零 msg（必须开）
OFFICIAL_RETRY_PARSES = False  # ★ 不需要「再点一次」
OFFICIAL_AUTO_HTTPS = False    # ★ 默认关：官方页不抢先探测，顺序交给壳
OFFICIAL_HTTPS_ONLY = True     # 仅在显式开启 AUTO_HTTPS 时生效
OFFICIAL_AUTO_TIMEOUT = 2

SITE = "https://m.98zb.com"
BASES = ["https://m.98zb.com", "https://m.98zhibo.com",
         "https://www.98zhibo.com", "https://www.98zb.com"]

# ======================================================================
# ★ 一级分类白名单：只列在这里的才会在 OK影视 顶部分类栏显示。
#   用户要求去掉：红框里的分类 + 直播 + 源自检 → 默认只留「完整比赛录像」入口。
#   想加回某个，把它的 key 追加进 SHOW_CATS 即可，其余代码不用动。
#   全部 17 个 key 对照：
#     today 今日视频 | live 直播 | nba NBA录像 | zuqiu 足球录像
#     cba CBA录像 | zonghe 综合录像 | nbajj NBA集锦 | zuqiujj 足球集锦
#     cbajj CBA集锦 | nbaqx 篮球球星 | zuqiuqx 足球球星
#     nba2 NBA | zuqiu2 足球 | cba2 CBA | zonghe2 综合
#     mobile 手机版 | diag 源自检
# ======================================================================
# ★★ 分类层三处调整（只在分类页生效；播放链路仍是 v7.5 原样，版本号不变）
#   ① 不显示「今日视频」：已从 SHOW_CATS 移除。
#   ② 录像分类尽量列全：放宽条目识别、规范分页 URL、读真实总页数。
#   ③ NBA 只显示「有国语回放」的比赛：腾讯国语/腾讯原声目前解不了，
#      留着也是点不开的卡片；国语回放 = 微博组，py 能直取 1080P。
#      代价：进 NBA 分类时并发抓若干详情页做判定（只在分类页发生，
#      homeContent / 启动路径仍零网络），结果缓存，同一场不重复抓。
#      抓不到的保守保留并标「未校验」，避免网络抖动误杀比赛。
#      不想做校验：把 NBA_ONLY_GUOYU 改成 False。
SHOW_CATS = ["nba", "zuqiu", "cba", "zonghe"]
_FALLBACK_TID = "zuqiu"       # 旧缓存请求 today / 未知 tid → 回落足球录像

# ======================================================================
# ★★ 国语回放校验（2026-11-23 修「昨天有效今天失效」）
#   旧版有个 9 秒整体上限，一到就 break，剩下没校验完的条目被【静默
#   放行】——连「未校验」标注都没有。源站一旦响应变慢，腾讯原声/国语
#   卡就整批混进来，看起来像筛选功能突然失效。另外 alt=False 只试一个
#   域名、抓不到还把 None 缓存住，一次网络抖动整场都放行。
#
#   现在：① 不提前 break，每条都尽量拿到判定；② 备用域名重试；
#   ③ 抓不到不缓存（下次刷新会重试）；④ 实在抓不到也不无条件放行，
#   按标题兜底把「明确只有腾讯/爱奇艺/优酷/咪咕」的卡剔掉，其余保留
#   并标「未校验」；⑤ 全程统计写进源自检，真机一眼能看出是哪一类。
# ======================================================================
NBA_ONLY_GUOYU = True
GUOYU_ONLY_CATS = {"nba"}     # 想让别的分类也过滤，加 zuqiu / cba / zonghe
GUOYU_CHECK_LIMIT = 30        # 每页最多校验条数（启动/分类提速）
GUOYU_WORKERS = 8             # 并发抓详情页数
GUOYU_TIMEOUT = 2             # 单条详情超时（秒）：分类最多等 8 秒，不再拖垮壳
GUOYU_RETRY = 0               # 不重试：一次抓不到按标题兜底，避免整批翻倍等待
GUOYU_TOTAL_TIMEOUT = 8       # 硬保护：点一次分类最多 8 秒
GUOYU_ALT = True              # ★ 允许换 BASES 备用域名，主域被拦也能抓到

# ======================================================================
# ★★ NBA 分类只看「近三天（含当天）」的比赛
#   目的：把要抓详情页做「国语回放」校验的条目数压到几条，分类页不再慢。
#   · 日期取自比赛标题：11月20日 / 2026年11月20日 / 11/20 / 2026/11/20
#   · 跨年跨月自动推断年份（12月31日 在 1月1日 仍算近三天）
#   · 比分「112-108」不会被误判成日期（只认中文月日 / 带 / 的格式）
#   · 没有日期的条目默认不保留（无法证明是近三天）；若真机上因此
#     条目偏少，把 NBA_RECENT_KEEP_NODATE 改成 True 即可。
#   · 生效时 NBA 分类 pagecount=1：近三天都在第一页，壳不翻页 → 最快。
# ======================================================================
NBA_RECENT_ON = True
RECENT_ONLY_CATS = {"nba"}    # 只作用于 NBA；想给足球也加就加 "zuqiu"
NBA_RECENT_DAYS = 3           # 含当天：今天 / 昨天 / 前天
NBA_RECENT_KEEP_NODATE = False
_TODAY_OVERRIDE = None        # 仅回归测试注入用；设备端永远是 None=当天

# ======================================================================
# ★★ 壳子预览页「更新推荐」= 与【NBA录像】分类栏下显示完全一致
#   用户确认：近三天「国语回放」场次不多，真机抓详情不慢 → 推荐页不再
#   图省事跳过校验，直接复用分类页的完整口径（近三天 + 国语回放校验 +
#   排除集锦/精华/十佳），两边逐条一致，不会再混进腾讯原声/腾讯国语。
#
#   实现：homeVideoContent 直接走 categoryContent("nba", 1)；分类页把
#   最终结果存进 _G["nba_final"]，推荐页优先复用它 → 点过分类后零请求。
#   ★★ 分类刷新后首页必须跟着更新：分类页每次成功刷新都会覆盖
#   nba_final 并把 nba_rev +1；推荐页【每次都以 nba_final 为准】，
#   不再拿自己那份旧快照短路返回，所以分类一更新、首页下次打开就是新的。
#   home_rev 记录首页同步到的版本号，源自检里可看到是否落后。
#   冷启动没缓存时才自己算一遍，且与分类页【完全同口径】(不再抓到即停)
#   （不为了挑条目最多去盲试全部兜底路径），把请求数压到最低。
#   断网/分类页失败 → 不增加版本号、保留上一次结果，首页不会被清空；
#   homeContent 的 4 个分类完全不受影响。
#
#   若真机上仍觉得慢：
#     · HOME_NBA_CACHE_ONLY=True → 纯零网络，只在点过 NBA 分类后才有推荐
#     · HOME_SHOW_NBA=False     → 回到空推荐
#     · HOME_NBA_SYNC_CAT=False → 退回旧轻量模式（不抓详情，但会混腾讯卡）
# ======================================================================
HOME_SHOW_NBA = True
HOME_NBA_SYNC_CAT = True      # ★ 默认：与 NBA 分类页完全一致（含国语回放校验）
HOME_NBA_LIMIT = 0            # 0 = 不裁剪，完全跟随分类页；>0 才截断
HOME_NBA_CACHE_ONLY = True    # ★ 首页主线程绝不【同步】抓网（防壳失去响应）
#   ★ 修「最近几版壳加载极慢/失去响应」：旧值 False 会让首页冷启动同步跑完整
#     categoryContent（首页+4 栏目候选+筛选版 30 个详情页），站点不通时主线程
#     阻塞 12~57 秒（筛选版理论最坏 387 秒）。现已收紧为后台预热 + 短等待。

# ★★ 「启动即有推荐」+「加载尽量快」：唯一能同时满足两者的做法。
#    init / homeContent（壳启动必调）起【1 个 daemon 后台线程】跑完整
#    categoryContent("nba", 1)，结果由它写入 _G["nba_final"]，
#    与分类页同一套取数逻辑 → 「推荐页 1 场 / 分类页 3 场」不会重演。
#    homeVideoContent 主线程最多等 HOME_WARM_WAIT 秒：拿到就显示最终列表；
#    没拿到就用同一份栏目页缓存【纯内存】出卡片（零网络），启动即有。
#    后台算完写 nba_final，壳下次刷新/再进首页自动收敛为最终结果。
#    ★ 主线程硬上限 0.8 秒，站点全不通也不会拖垮壳；不写文件、不起服务、
#      无需额外进程，daemon 随壳进程结束。
HOME_WARM_ON = True            # False = 回到「启动空推荐、点分类才有」的排障行为
HOME_WARM_WAIT = 0.8           # 主线程最多等待秒数；站点极慢可调 1.2，仍远低于旧版

# 下面两个是旧轻量模式的兼容变量；SYNC_CAT=True 时由分类页的
# NBA_RECENT_ON / NBA_ONLY_GUOYU 决定，这里不生效，保留避免旧配置报错。
HOME_NBA_TIMEOUT = 2
HOME_NBA_RECENT = True

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
_VISIBLE_CATS = [c for c in _CATS if c[0] in set(SHOW_CATS)]

# 导航学习失败时的兜底栏目路径；会逐个试，取比赛条目最多的那份。
_CAT_FALLBACKS = {
    "nba":    ["/nbalx/", "/nbalx/list_175_1.html", "/nba/"],
    "zuqiu":  ["/zqlx/", "/zqlx/list_208_1.html", "/football/"],
    "cba":    ["/cbalx/", "/cbalx/list_180_1.html", "/cba/"],
    "zonghe": ["/zhlx/", "/zhlx/list_196_1.html", "/zonghe/"],
}


def _norm(s):
    return re.sub(r'[\s\W_]+', '', str(s or '')).lower()

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

# 腾讯/爱奇艺/优酷/咪咕等「官方页」：浏览器能播试看，但要广告+登录/会员，
# 服务端 HTML 里没有直链；py 与通用解析都不解鉴权，只能交壳 WebView 渲染。
_OFFICIAL_PAGE = re.compile(
    r'(?:^|\.)(?:v\.qq|sports\.qq|qq|iqiyi|youku|mgtv|pptv|le|sohu|'
    r'cntv|cctv|miguvideo|migu|kandian)\.com(?::\d+)?$', re.I)

# ★★ 从「任意文本」抠官方播放页：不只 <a href>，还要覆盖
#   iframe src / JS location.href / var url='...' / ?url= / \/ 转义 / 百分号编码
# 98 这类导航站常用中转页包一层，只抓 <a> 会把官方页漏掉，
# 结果把 98 中转页交给壳 → 壳不认域名 → 「播放地址解析失败」。
_OFFICIAL_HOSTS = (r'(?:[a-z0-9-]+\.)*'
                   r'(?:v\.qq|sports\.qq|qq|iqiyi|youku|mgtv|pptv|le|sohu|'
                   r'cntv|cctv|miguvideo|migu|kandian)\.com')
_OFFICIAL_URL_RE = re.compile(
    r'https?://' + _OFFICIAL_HOSTS + r'(?::\d+)?(?:/[^\s"\'<>\\)]*)?', re.I)

# 播放源分组名（腾讯国语 / 腾讯原声 / 爱奇艺 …）用来判断这是「官方线路」。
# 国语回放(微博) 不含这些词，不会被误判。
_OFFICIAL_GROUP = re.compile(
    r'腾讯|爱奇艺|奇艺|优酷|咪咕|芒果|PPTV|乐视|搜狐|央视|CCTV|原声',
    re.I)

# ======================================================================
# ★★ CCTV国语：央视网页面 → py 内取「超清」2000 档 → parse=0 直连
#   依据（用户真机 HAR，2026-11-26「央视国语-响应.txt」）：
#     sports.cctv.com/.../VIDE*.shtml
#       → vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=<32位hex>  (200/23.6KB)
#       → dh5ws01.v.cntv.cn/asp/h5e/hls/main/.../<pid>/main.m3u8?maxbr=2048
#       → 四档 2000 / 1200 / 850 / 450 .m3u8
#   埋点 bit=2048000 ↔ 2000 档 = 播放器菜单【超清】；bit=1228800 ↔ 1200 = 高清。
#   ★★ 用户提供的 main.m3u8 实证：四档 450/850/1200/2000，其中
#      2000 档 BANDWIDTH=2048000 RESOLUTION=1280x720。
#      官网菜单「超清」= 高码率 720P，源本身【没有 1080P】。
#      自动选超清 = GET 主清单按 BANDWIDTH 取最高档子清单，不硬拼路径。
#   ★★ 花屏根因：HAR 里 /h5e/ 走腾讯云 VOD 私有加密
#      （wss://signal.qvb.qcloud.com + conf.qvb 435B 二进制配置 +
#       HTML5_VOD_DRM_PLAYER + jsencrypt.js，.key/license 均 0 条），
#      官网 JS 用 SDK 解密 TS，壳裸解 → 绿色马赛克花屏（音频轨独立故有声）。
#      API 的 hls_url = /asp/hls/ 普通未加密流，优先用它；h5e 降为兜底。
#   ★ 主清单绝不交给播放器（否则按带宽选 450 档 → 480P）；
#      子档 URL 一律由主清单给出，urljoin 后 GET 校验是单档才交。

#   ★ 镜像域名 dh5wx.cntv.kfcbest.com 同路径可用（HAR 四档均 200）。
#   ★ Referer 必须 https://sports.cctv.com/（HAR 全部请求一致）。
#   ★ 全程不需要解析池 / 不需要 jx / 不需要 flag，与「国语回放」同形态。
# ======================================================================
CCTV_SUPER_BR = "2000"          # 官网菜单「超清」档名（仅日志用，不拼路径）
CCTV_DIRECT_ON = True
#   ★ 若设备解码器仍花屏：改 False 即退回「极简交壳」，是唯一确定的无花屏状态
CCTV_HLS_HOST = "https://hls.cntv.lxdns.com"   # hls_cdn_info.cdn_vip：普通未加密 HLS
CCTV_API_FULL = ("https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=%s"
                 "&client=flash&im=0&tsp=%s&vn=2049&vc=%s&uid=%s&wlan=")
CCTV_API_VC = "02AA4192D588176DFE3490ED4AD7B605"   # HAR 实证参数（服务端不校验时可用）
CCTV_API_UID = "3A75FF44FA3267FD20B26CCFE86814E7"
CCTV_HOST_RE = re.compile(
    r'(?:sports\.cctv|tv\.cctv|news\.cctv|v\.cctv|cctv|cntv|'
    r'vdn\.apps\.cntv|dh5ws01\.v\.cntv|dh5wx\.cntv)\.(?:com|cn)', re.I)
CCTV_PID_RE = re.compile(r'(?<![a-f0-9])([a-f0-9]{32})(?![a-f0-9])', re.I)
CCTV_API = "https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid="
CCTV_CDNS = ["https://dh5ws01.v.cntv.cn",       # h5e 域名，保留供日志/排障
             "https://dh5wx.cntv.kfcbest.com"]

CCTV_REF = "https://sports.cctv.com/"
_CCTV_GROUP = re.compile(r'cctv|央视|cntv', re.I)


def _is_cctv(u):
    """是否央视/央视网域名（央视国语线路、页面、API 都算）。"""
    s = str(u or "")
    if not s.startswith("http"):
        return False
    try:
        host = urllib.parse.urlsplit(s).hostname or ""
    except Exception:
        return False
    return bool(CCTV_HOST_RE.search(host))


def _cctv_pid(page, html=""):
    """抠央视视频 pid：URL ?pid= → 页面内嵌 32 位 hex（videoCenterId/guid）。"""
    m = re.search(r'[?&]pid=([a-f0-9]{32})', str(page), re.I)
    if m:
        return m.group(1)
    for src in (html, page):
        for m in CCTV_PID_RE.finditer(str(src or "")):
            return m.group(1)
    return ""


def _cctv_hls_list(src):
    """从 API 响应 / 页面 / URL 文本里抠出所有 m3u8 地址（还原反斜杠与斜杠转义）。"""
    t = _unesc(str(src or ""))
    out = []
    for u in re.findall(r'https?://[^\s"\'<>\\)，；]+', t):
        if '.m3u8' in u.lower():
            out.append(u.rstrip('\\",;'))
    return out


def _cctv_master_rank(u):
    """主清单优先级（API manifest + HAR 实证）。

    API 响应同时给出 5 个 HLS 变体：
      hls_url          /asp/hls/main/...       ← 普通，非 enc、非 h5e，首选
      manifest.hls_enc2_url   /asp/enc2/hls/...
      manifest.hls_h5e_url    /asp/h5e/hls/...  ← 官网 133 条请求全走它
      manifest.hls_enc_url    /asp/enc/hls/...
      manifest.hls_audio_url  /asp/hlsaudio/...  ← 纯音频，排除
    ★★ 花屏根因：/h5e/ 是腾讯云 VOD 私有加密流。HAR 里有
      wss://signal.qvb.qcloud.com + conf.qvb.qcloud.com/vod/h5 435B 二进制配置
      + HTML5_VOD_DRM_PLAYER + jsencrypt.js，且 .key / license 请求均为 0 条
      → 不是标准 AES-128，是官网 JS 用 SDK 解密 TS。壳播放器拿到裸 TS
      直接解码就是【绿色马赛克花屏】，而音频轨独立所以「有声音」。
    ★ 因此默认优先走未加密的普通 /asp/hls/，/h5e/ 降为兜底。
    """
    s = str(u or "")
    low = s.lower()
    if 'audio' in low or 'mp3' in low:
        return 90                                  # 纯音频，排除
    if '/asp/hls/' in low and '/h5e/' not in low and '/enc' not in low:
        return 0                                   # 普通未加密，首选
    if '/enc2/' in low:
        return 1
    if '/h5e/' in low:
        return 2                                   # 私有加密，降为兜底
    if '/enc/' in low:
        return 3
    return 4


def _cctv_ok(u, timeout=3):
    """硬约束：只认【单档媒体清单】，多码率主清单一律拒绝。

    ★ 主清单也含 #EXTM3U，交出去播放器会按带宽自己选 450 档 → 480P。
    """
    if not u:
        return False
    try:
        h, _f = _fetch(u, ref=CCTV_REF, timeout=timeout, alt=False)
    except Exception:
        return False
    if not h:
        return False
    head = h[:2000]
    if '#EXT-X-STREAM-INF' in head:
        return False
    return ('#EXTM3U' in head and
            ('#EXTINF' in h[:8000] or '#EXT-X-TARGETDURATION' in head))


def _cctv_variants(main, h):
    """解析主清单所有档位，按 BANDWIDTH 降序返回【服务端写明的】子档 URL。

    ★★ 不再硬拼 /hls/<档位>/ 路径。用户提供的 main.m3u8 实证：
         #EXT-X-STREAM-INF:PROGRAM-ID=1, BANDWIDTH=2048000, RESOLUTION=1280x720
         /asp/h5e/hls/2000/0303000a/3/default/<pid>/2000.m3u8
       子档地址由主清单自己给出，urljoin 即可；域名/目录改了自动跟随。
    ★ 2000 档 RESOLUTION=1280x720：官网菜单「超清」= 高码率 720P，
      源本身【没有 1080P】。按 BANDWIDTH 取最高档就是「自动选超清」。
    """
    lines = [x.strip() for x in h.splitlines() if x.strip()]
    out = []
    for i, ln in enumerate(lines):
        if not ln.startswith('#EXT-X-STREAM-INF'):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not nxt or nxt.startswith('#'):
            continue
        mb = re.search(r'BANDWIDTH=(\d+)', ln)
        bw = int(mb.group(1)) if mb else 0
        mr = re.search(r'RESOLUTION=\d+x(\d+)', ln, re.I)
        hh = int(mr.group(1)) if mr else 0
        u = nxt if nxt.startswith('http') else urllib.parse.urljoin(main, nxt)
        out.append((bw, hh, u))
    out.sort(key=lambda x: -x[0])
    return out


def _cctv_api_info(pid, timeout=5):
    """取 API 响应正文：简版优先，缺 hls_url/manifest 时带 HAR 实证参数重试。

    ★ 用户提供的 23604B 完整响应来自带 client=flash&vn=2049&vc&uid 的请求；
      HAR 里那些 2533B 小响应是 segments 精彩片段（pid 是片段 guid），不是主片。
      简版 ?pid= 是否返回完整 JSON 无法本地实测，故做两级：
      先简版（快），响应里没有 hls_url/manifest/m3u8 再试完整参数版。
      vc/uid 是 HAR 快照值；服务端不校验时可用，校验失败会退回简版内容。
    """
    if not pid:
        return ""
    urls = [CCTV_API + pid]
    try:
        urls.append(CCTV_API_FULL %
                    (pid, str(int(time.time())), CCTV_API_VC, CCTV_API_UID))
    except Exception:
        pass
    best = ""
    for u in urls:
        try:
            h, _f = _fetch(u, ref=CCTV_REF, timeout=timeout, alt=False)
        except Exception:
            h = ""
        if not h:
            continue
        if not best:
            best = h
        if '"hls_url"' in h or '"manifest"' in h or '.m3u8' in h:
            return h
    return best


def _cctv_resolve(page, timeout=5):
    """CCTV国语 → 【校验通过】的最高档单清单直链。返回 (url 或 None, 日志)。

    ★ 修「花屏」：优先 API 的 hls_url（/asp/hls/ 普通未加密流），
      /h5e/ 私有加密流降为兜底。不再把官网 JS 才解得开的 TS 直接交给壳。
    ★ 修「480P」：GET 主清单 → 按 BANDWIDTH 降序取最高档子清单 →
      逐个 GET 校验是单档；主清单绝不外泄，播放器无从自己降档。
    ★ 不再硬拼档位目录；子档 URL 全部由服务端主清单给出。
    ★ 正常路径：页面(仅缺 pid 时) + API + 主清单 + 1 次子档校验 = 3 请求，
      不会拖慢起播；全失败返回 None → 极简交壳，不吐 404 / 不黑屏。
    """
    log = []
    pid = _cctv_pid(page)
    html = ""
    if not pid:
        try:
            h, _f = _fetch(page, ref=CCTV_REF, timeout=timeout, alt=False)
            html = h or ""
        except Exception:
            html = ""
        pid = _cctv_pid(page, html)
    if pid:
        log.append("pid=" + pid)
    info = _cctv_api_info(pid, timeout)
    if info:
        log.append("API 响应 %d 字节" % len(info))
    masters = []
    for src in (info, html, page):
        masters += _cctv_hls_list(src)
    # 兜底：pid 已知但 API/页面都没给清单 → 普通未加密 /asp/hls/ 主清单
    if pid and not any(_cctv_master_rank(u) < 90 for u in masters):
        masters.append("%s/asp/hls/main/0303000a/3/default/%s/main.m3u8?maxbr=2048"
                       % (CCTV_HLS_HOST, pid))
    uniq = list(dict.fromkeys([u for u in masters if u]))
    uniq.sort(key=_cctv_master_rank)
    log.append("主清单候选(优先级) " + ", ".join(
        "%d:%s" % (_cctv_master_rank(u),
                   u.split('/')[2] if '://' in u and len(u.split('/')) > 2 else u[:16])
        for u in uniq[:4]))
    for main in uniq[:5]:
        if _cctv_master_rank(main) >= 90:
            continue
        try:
            h, _f = _fetch(main, ref=CCTV_REF, timeout=timeout, alt=False)
        except Exception:
            h = ""
        if not h:
            log.append("主清单取不到 " + main[:100])
            continue
        if '#EXT-X-STREAM-INF' in h:
            vs = _cctv_variants(main, h)
            log.append("档位(高→低) " + ", ".join(
                "%d/%dp→%s" % (bw, hh, u.split('/')[-1]) for bw, hh, u in vs[:4]))
            for bw, hh, sub in vs[:4]:
                if _cctv_ok(sub, 3):
                    log.append("★ 选最高可播档 %d/%dp(单档·已校验) " % (bw, hh)
                               + sub[:110])
                    return sub, log
            log.append("各档单清单校验未过 " + main[:90])
        elif _cctv_ok(main, 3):
            log.append("★ 主清单本身即单档 " + main[:100])
            return main, log
    log.append("所有变体均未产出可播单档（主清单已拒绝，不会自动降 480P）")
    return None, log

# ======================================================================
# ★ 二级/三级目录过滤：排除「十佳 / 集锦 / 精华」等非完整比赛条目
#   二级 = 分类列表里的比赛卡片（_items）
#   三级 = 详情页里的分节选集（_episodes）
#
#   命中即丢弃（子串匹配，覆盖常见变体）：
#     集锦/锦集/集绵、全场集锦、进球集锦、赛后集锦、本场集锦、集锦回放
#     精华/精华版/全场精华、精华回放、赛事精华
#     十佳/十佳球/十佳进球、五佳/五佳球、TOP10
#     高光/高光时刻、花絮、纯享、看点、混剪、剪辑、盘点
#     highlights / condensed（英文标题）
#   「精彩」只在组合词（精彩瞬间/镜头/回放/时刻/十佳球…）里排除，
#    避免误杀「精彩全场录像回放」这类正经完整比赛标题。
#
#   ★ 一定保留：全场录像回放 / 全场回放 / 第X节录像 / 完整版 / 加时
#   ★ 想专门看集锦：把 DROP_HIGHLIGHTS 改成 False 即可，无需改别处。
# ======================================================================
DROP_HIGHLIGHTS = True
_HIGHLIGHT_SKIP = re.compile(
    r'集锦|锦集|集绵|精华|十佳|五佳|高光|花絮|纯享|看点|'
    r'混剪|剪辑|盘点|进球集锦|集锦回放|精华回放|'
    r'精彩(?:瞬间|镜头|回放|时刻|集锦|球|十佳|进球)|'
    r'TOP\s*\d+|highlights?|condensed', re.I)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

# 模块级状态（无 __init__，避免触发基类初始化）
_G = {"home": None, "learned": False, "cat_url": {},
      "wb_visitor": "", "wb_log": [],
      "cfg_parses": [], "parses": None, "parses_note": "",
      "parse_ext": {}, "sub_urls": [], "ext_subs": [], "cfg_files": [],
      "sub_parses": None, "sub_note": "", "sub_key": "",
      "parse_cursor": 0, "parse_last": {}, "parse_used": "",
      "parse_probe_log": [], "parse_round": 0, "parse_dead": False,
      "shell_turn": {},      # 非官方页：0→先壳 / 1→下轮试订阅parses
      "official_turn": {},   # 兼容保留
      "official_trace": [],  # ★ 上一次官方线路「还原真实官方页」的链路日志
      "guoyu_cache": {},    # ★ 详情页是否有「国语回放」分组（只缓存 True/False）
      "guoyu_stat": {},     # ★ 本轮校验统计 + 逐条判定，源自检可见
      "nba_page": None,     # ★ 已抓到的 NBA 栏目页（首页推荐复用，零重复请求）
      "nba_final": None,    # ★ NBA 分类页【最终列表】→ 推荐页逐条复用，完全一致
      "nba_rev": 0,        # ★ NBA 分类页成功刷新次数（每次 +1）
      "home_rev": -1,      # ★ 「更新推荐」上次同步到的分类版本号
      "home_sync": False,   # ★ 推荐页调用中：栏目页抓到即停，少发请求
      "home_nba": None,     # ★ 「更新推荐」上次返回快照（仅供自检显示）
      "title_full": {},     # ★ href -> 完整原名（详情页/搜索用，短名不丢信息）
      "warm_started": False}  # ★ 后台预热线程已启动（整个进程只 1 个）


# 预热完成事件放模块级（不放 _G，_G 保持全可序列化）；daemon 线程只启一次。
_WARM_LOCK = threading.Lock()
_WARM_EVT = threading.Event()


def _start_warm(spider):
    """壳启动即异步预热「更新推荐」：只起 1 个 daemon 线程跑完整
    categoryContent("nba", 1)，结果由它写入 _G["nba_final"]。

    ★ 为什么能同时满足「启动即有」+「加载快」：
      · 所有网络都在后台线程，主线程（壳 UI）零阻塞；
      · homeVideoContent 最多等 HOME_WARM_WAIT 秒，站点不通也立即返回；
      · 与分类页共用同一套逻辑，nba_final 是唯一真相，一致性不破；
      · 不写任何本地文件、不起服务、无需额外进程，随壳进程生命周期结束。
    ★ 幂等：init 与 homeContent 都会调，锁保证只启 1 次。
    """
    if not HOME_WARM_ON or _G.get("warm_started"):
        return
    with _WARM_LOCK:
        if _G.get("warm_started"):
            return
        _G["warm_started"] = True

        def _run():
            try:
                spider.categoryContent("nba", 1, False, {})
            except Exception:
                pass
            finally:
                try:
                    _WARM_EVT.set()
                except Exception:
                    pass

        try:
            t = threading.Thread(target=_run, name="zb98-warm", daemon=True)
            t.start()
        except Exception:
            # 极少数壳禁用后台线程：退回「启动空、点分类即有」，绝不卡主线程
            _G["warm_started"] = False
            _WARM_EVT.set()


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
        for b in BASES[1:2]:
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


# ★ 国语回放判据：正面词只认「国语回放 / 中文解说 / 微博」这类完整写法，
#   不认光秃秃的「国语」——否则「腾讯国语」会被误判成有国语回放。
_GUOYU_POS = re.compile(
    r"国语\s*回放|\[\s*国语(?:回放)?\s*\]|【\s*国语(?:回放)?\s*】|"
    r"中文解说|国语解说|微博回放|微博|"
    r"CCTV\s*国语|央视\s*国语|cctv|cntv|央视网|央视体育", re.I)
# ★ CCTV国语 也是 py 能直连的线路，不能再算「明确只有官方页」。
#   原正则里的「央视|CCTV」已移除，否则含央视的分组会被误杀。
_GUOYU_OFF = re.compile(
    r"腾讯|原声|爱奇艺|优酷|咪咕|migu|iqiyi|youku|mgtv|芒果", re.I)
# 98 的「国语回放」分组固定指向微博正文（weibo.com/uid/mid），
# 分组文案怎么改这个特征都在；分享链接 service.weibo.com 不匹配。
_WB_POST_RE = re.compile(
    r"https?://(?:m\.)?weibo\.(?:com|cn)/\d+/[A-Za-z0-9]+"
    r"|https?://m\.weibo\.cn/(?:status|detail)/", re.I)


def _title_guoyu_hint(t):
    """抓不到详情页时的标题兜底：True=明确有 / False=明确只有官方页 / None=看不出。"""
    s = str(t or "")
    if _GUOYU_POS.search(s):
        return True
    if _GUOYU_OFF.search(s):
        return False
    return None


# ======================================================================
# ★ 卡片标题精简：壳的预览卡片只显示 2 行，98 原标题太长一眼看不全。
#   短名 = 日期 + 对阵（如「11月24日 湖人vs勇士」），两行即可看全；
#   完整原名移到 vod_remarks（备注）和详情页标题 / 正文，信息不丢。
#   ★ 短名【必须保留日期】：近三天过滤 _recent_ok 读的是 vod_name。
#   ★ 完整原名进 remarks 后，标题兜底与搜索要同时看 name + remarks。
# ======================================================================
SHORT_TITLE = True          # 关掉 = 恢复原来的完整标题

_SHORT_DATE = re.compile(
    r"20\d{2}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日|"
    r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}")
_SHORT_VS = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9]{1,10})\s*(?:vs|VS|Vs|vS|对阵)\s*"
    r"([\u4e00-\u9fa5A-Za-z0-9]{1,10})")


def _short_title(t):
    """把 98 的长标题压成「日期 + 对阵」；抽不到就退化为前半截，绝不空。"""
    s = str(t or "").strip()
    if not SHORT_TITLE or not s:
        return s
    d = _SHORT_DATE.search(s)
    v = _SHORT_VS.search(s)
    date = re.sub(r"^20\d{2}年", "", d.group(0)) if d else ""
    game = (v.group(1) + "vs" + v.group(2)) if v else ""
    if date and game:
        return (date + " " + game)[:26]
    if game:
        return game[:26]
    if date:
        rest = s.replace(date, "", 1).strip(" ·-_[]【】")
        return (date + " " + rest)[:22].strip() or date
    return s[:22].strip() or s


# ======================================================================
# 解析兜底：读取「当前播放线路的 json / txt」里的 parses 数组
#   典型 TVBox / OK影视 配置：
#   {"sites":[...], "parses":[{"name":"聚合","url":"https://jx.x.com/?url=",
#                              "type":0}, ...]}
#   ★ 纯本地文件读取，绝不发网络请求；只在需要兜底时才惰性执行。
# ======================================================================
def _candidate_files():
    """★ 不扫描本机目录。只认【显式指定】的订阅文件：
       ① PARSES_FILE（py 顶部常量）
       ② ext 里带进来的本机订阅路径（subscribe / parses_file / configFile）
       ③ SUBSCRIBE_URLS 是网络地址，由 _pull_subscribe 单独处理
    """
    out = []
    raw = [str(PARSES_FILE or "").strip()] + \
          [str(x) for x in (_G.get("cfg_files") or [])]
    for p in raw:
        if not p:
            continue
        if p.startswith("file://"):
            p = p[7:]
        try:
            p = os.path.abspath(os.path.expanduser(p))
            if os.path.isfile(p) and p not in out:
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


def _is_official(page):
    return bool(_OFFICIAL_PAGE.search(_host(page)))


# 壳解析项 ext.flag 常用的平台标记；回传它可帮壳匹配到自带解析。
_OFFICIAL_FLAGS = [
    (re.compile(r'qq\.com$', re.I), "qq"),
    (re.compile(r'iqiyi\.com$', re.I), "iqiyi"),
    (re.compile(r'youku\.com$', re.I), "youku"),
    (re.compile(r'mgtv\.com$', re.I), "mgtv"),
    (re.compile(r'pptv\.com$', re.I), "pptv"),
    (re.compile(r'sohu\.com$', re.I), "sohu"),
    (re.compile(r'(?:migu|miguvideo|cntv|cctv)\.com$', re.I), "migu"),
]


def _official_flag(page):
    h = _host(page)
    for rx, fl in _OFFICIAL_FLAGS:
        if rx.search(h):
            return fl
    return ""


def _official_urls(text, base=""):
    """★ 从任意文本抠出「真实官方播放页」，覆盖 <a>/iframe/JS/?url=/转义。

    返回按可信度排序的去重列表：带 vid/mid/cover/id= 的排最前。
    98 中转页里如果没有 <a href>，靠这个函数仍能拿到 v.qq.com 地址。
    """
    raw = _unesc(str(text or ""))
    # 百分号编码过的整段 url 也要还原（?url=https%3A%2F%2Fv.qq.com%2F...）
    try:
        dec = urllib.parse.unquote(raw)
        if dec != raw:
            raw += "\n" + dec
    except Exception:
        pass
    out, seen = [], set()
    for m in _OFFICIAL_URL_RE.finditer(raw):
        u = _abs(m.group(0).rstrip(".,;:)\"'\u3002"), base)
        if not u or not _is_official(u) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    def score(u):
        q = urllib.parse.urlsplit(u)
        blob = (q.path + "?" + q.query).lower()
        s = 0
        for k in ("cover", "/vid", "vid=", "mid=", "/v_", "id=", "cid=",
                  "kbsweb", "game.htm", "/x/", "page"):
            if k in blob:
                s += 2
        # 太短的首页/根路径多半是推广链接，降权
        if len(q.path.rstrip("/")) < 4:
            s -= 3
        return -s
    return sorted(out, key=score)


def _resolve_official(target, headers):
    """★★ 把「官方线路」还原成真实官方页再交壳（v7.5 核心修正）。

    用户点的是腾讯国语/腾讯原声，但 98 详情页给的常是本站中转页：
      · <a href> 只是壳，真实页在 iframe src / JS / ?url= 里
      · 或直接 302 到官方页
    只抓 <a> 时抽不到 → 把 98 中转页交壳 → 壳不认域名 → 「播放地址解析失败」。
    这里依次尝试：target 自身 → query 内嵌 → fetch 后 final url → 整页 HTML。
    全程把链路写进 _G['official_trace']，供「源自检」零网络回显。
    """
    tr = _G.setdefault("official_trace", [])
    tr.clear()
    tr.append("原始 target: " + str(target)[:160])
    hd = dict(headers or {})

    # ① target 自身或它的 query 里就有官方页
    cands = _official_urls(target, SITE + "/")
    tr.append("target/query 内抠到官方页: %d 条" % len(cands))

    # ② 98 中转页：抓一次，先看 302 后的 final url，再扫整页 HTML
    if not cands and _is98(target):
        try:
            h, final = _fetch(target, ref=SITE + "/", timeout=4)
            tr.append("中转页 fetch: %s / final: %s" %
                      ("成功 %d 字" % len(h) if h else "无内容",
                       str(final)[:120] or "无"))
            if final and _is_official(final):
                cands.append(final)
                tr.append("final(302) 命中官方页")
            if h:
                found = _official_urls(h + "\n" + str(final or ""), final or target)
                tr.append("整页 HTML 抠到官方页: %d 条" % len(found))
                for u in found:
                    if u not in cands:
                        cands.append(u)
        except Exception as e:
            tr.append("中转页 fetch 异常: " + str(e)[:70])

    if cands:
        real = cands[0]
        tr.append("★ 最终交壳: " + real[:160])
        for i, u in enumerate(cands[1:4]):
            tr.append("   备选[%d]: %s" % (i + 1, u[:140]))
        _G["parse_used"] = "官方线路→还原真实官方页→壳解析"
        return _official_to_shell(real, hd)

    # ③ 实在抽不到：仍交壳（交给 final url 优先），但把原因记清楚
    tr.append("⚠ 未抠到官方页，交壳的是中转页 —— 壳很可能报解析失败")
    tr.append("   请把以上几行发给作者，用于补一条中转页规则")
    _G["parse_used"] = "官方线路→未抠到真实官方页(交中转页)"
    return _clean_shell(target, hd)


def _page_url(u, n):
    """DedeCMS 数字分页：list_208_1.html → list_208_<n>.html。"""
    if not u:
        return ""
    mm = re.search(r"(list_\d+_)(\d+)(\.html?)$", u, re.I)
    if mm:
        return u[:mm.start()] + mm.group(1) + str(n) + mm.group(3)
    return ""


def _next_page(html, base):
    """从分类页里找「下一页」链接（兼容 » / 下页 / 末页）。"""
    for href, text in _links(html or "", base or ""):
        if _text(text) in ("下一页", "下页", "»", "末页", ">"):
            return href
    return ""


def _max_page(html, base):
    """★ 从分类页里读真实总页数：数字页码链接 + list_N_<n>.html + 「共N页」。
    旧版只靠「有没有下一页」猜，pagecount 恒为 2，壳翻两页就停，
    足球录像自然比原站少一大截。"""
    mx = 1
    for href, inner in _links(html or "", base or ""):
        mm = re.search(r'list_\d+_(\d+)\.html?', href, re.I)
        if mm:
            try:
                mx = max(mx, int(mm.group(1)))
            except Exception:
                pass
        t = _text(inner).strip()
        if t.isdigit() and 1 <= int(t) <= 99:
            mx = max(mx, int(t))
    mm = re.search(r'(?:共|总)\s*(\d{1,3})\s*页', html or "")
    if mm:
        try:
            mx = max(mx, int(mm.group(1)))
        except Exception:
            pass
    return min(mx, 30)


def _canon_cat_url(u, html, base):
    """★ 把分类 URL 规范成 list_N_1.html，让 _page_url 能直接算第 n 页。
    目录首页（/zqlx/）没有数字页码时翻页只能靠「下一页」链逐跳，很慢。"""
    for href, _t in _links(html or "", base or ""):
        if _is98(href) and re.search(r'list_\d+_1\.html?$', href, re.I):
            return href
    m = re.search(r'https?://[^\s"\'<>]+/list_\d+_1\.html?', html or "", re.I)
    if m:
        return _abs(m.group(0), base)
    return u


def _recent_ok(title, now=None):
    """★ 标题里的日期是否落在「近 NBA_RECENT_DAYS 天（含当天）」。

    支持：11月20日 / 2026年11月20日 / 11/20 / 2026/11/20。
    年份缺省时试 去年/今年/明年，跨年跨月都能对上（12月31日 vs 1月1日）。
    不认 112-108 这类比分（中文月日或斜杠格式才认）。
    没解析出日期 → 由 NBA_RECENT_KEEP_NODATE 决定。
    """
    d0 = now or _TODAY_OVERRIDE or date.today()
    lo = d0 - timedelta(days=max(NBA_RECENT_DAYS, 1) - 1)
    s = str(title or "")
    cand = []
    # 2026年11月20日
    for m in re.finditer(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s):
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    # 11月20日（年份靠候选推断）
    for m in re.finditer(r'(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日', s):
        mo, dd = int(m.group(1)), int(m.group(2))
        for yy in (d0.year - 1, d0.year, d0.year + 1):
            cand.append((yy, mo, dd))
    # 2026/11/20
    for m in re.finditer(r'(?<!\d)(20\d{2})/(\d{1,2})/(\d{1,2})(?!\d)', s):
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    # 2026-11-23（带年份三段式横线；不会误认「112-108」这类两段比分）
    for m in re.finditer(r'(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)', s):
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    # 11/20（斜杠；横线留给比分，不认）
    for m in re.finditer(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)', s):
        mo, dd = int(m.group(1)), int(m.group(2))
        for yy in (d0.year - 1, d0.year, d0.year + 1):
            cand.append((yy, mo, dd))
    if not cand:
        return bool(NBA_RECENT_KEEP_NODATE)
    for yy, mo, dd in cand:
        try:
            d = date(yy, mo, dd)
        except Exception:
            continue
        if lo <= d <= d0:
            return True
    return False


# ======================================================================
# ★ 播放页「视频源分组」按比赛日期分叉排序（两套互斥，用户口径）：
#   最近三天（含当天）距今 0/1/2 天
#       → 国语回放 → CCTV国语 → 腾讯国语 → 腾讯原声
#   三天以前（含当天/第3天）距今 >= 3 天
#       → CCTV国语 → 腾讯国语 → 腾讯原声 → 国语回放
#   ★ 分界只由 OLD_SORT_AFTER_DAYS 一个数字决定；日期解析不出按近比赛处理。
#   ★ 这个阈值【只管播放页分组顺序】，与 NBA_RECENT_DAYS（分类页/更新推荐
#      的「近三天显示」过滤）互相独立：两个数字各管一件事。
#   ★ 只重排分组，不删任何线路；其余分组（爱奇艺/优酷/咪咕…）保持原相对顺序。
# ======================================================================
OLD_SORT_ON = True
OLD_SORT_AFTER_DAYS = 3
OLD_SORT_ORDER = ["CCTV国语", "腾讯国语", "腾讯原声", "国语回放"]
NEAR_SORT_ORDER = ["国语回放", "CCTV国语", "腾讯国语", "腾讯原声"]


def _reorder_groups(items, names):
    """稳定地把 names 里的分组按序提到前面；名单外保持原相对顺序。
    央视别名（央视国语/CCTV…）归到「CCTV国语」那一位。"""
    n = len(names)
    ci = names.index("CCTV国语") if "CCTV国语" in names else n

    def key(g):
        s = str(g or "")
        for i, kw in enumerate(names):
            if kw in s:
                return i
        if ci < n and _CCTV_GROUP.search(s):
            return ci
        return n
    return sorted(list(items), key=lambda kv: key(kv[0]))


def _game_days(title, now=None):
    """比赛距今天的天数；解析不出日期返回 None（保守不改排序）。

    与 _recent_ok 用同一套日期格式（中文月日 / 带年份 / 斜杠 / 横线），
    缺年份时试 去年/今年/明年，跨年跨月都能对上。
    ★ 已有带年份的完整日期时，不再用「11月20日」这类无年份正则二次解析：
      否则「2026年11月30日」会被补出一个「2025年11月30日」候选(359天前)，
      把未来的比赛误判成老比赛。
    ★ 未来日期一律跳过，不会被当成老比赛。
    """
    d0 = now or _TODAY_OVERRIDE or date.today()
    s = str(title or "")
    cand = []
    has_year = False
    for m in re.finditer(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s):
        has_year = True
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in re.finditer(r'(?<!\d)(20\d{2})/(\d{1,2})/(\d{1,2})(?!\d)', s):
        has_year = True
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in re.finditer(r'(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)', s):
        has_year = True
        cand.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not has_year:
        for m in re.finditer(r'(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日', s):
            mo, dd = int(m.group(1)), int(m.group(2))
            for yy in (d0.year - 1, d0.year, d0.year + 1):
                cand.append((yy, mo, dd))
        for m in re.finditer(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)', s):
            mo, dd = int(m.group(1)), int(m.group(2))
            for yy in (d0.year - 1, d0.year, d0.year + 1):
                cand.append((yy, mo, dd))
    if not cand:
        return None
    best = None
    for yy, mo, dd in cand:
        try:
            d = date(yy, mo, dd)
        except ValueError:
            continue
        delta = (d0 - d).days
        if delta < 0:                 # 未来日期不误判成老比赛
            continue
        if best is None or delta < best:
            best = delta
    return best


def _old_group_rank(g):
    """老比赛的分组排序键；不在指定名单里的分组一律排在最后。"""
    s = str(g or "")
    for i, kw in enumerate(OLD_SORT_ORDER):
        if kw in s:
            return i
    if _CCTV_GROUP.search(s):      # 央视/央视国语/CCTV 别名 → 老比赛同样第 1 位
        return 0
    return len(OLD_SORT_ORDER)

def _clean_shell(page, hd, prefix=""):
    """★★ 极简交壳返回：只留标准三件套，绝不写 msg。
    壳会把 playerContent 的 msg 当「播放失败原因」弹出 ⚠ 页并中断解析，
    这就是截图里「已交 OK影视 壳子解析」那行字的来源。"""
    out = {"parse": 1, "url": page, "header": hd}
    if prefix:
        out = {"parse": 0, "url": prefix + page, "header": hd}

    # ★★★ 真机「点腾讯国语没有解析名字、没播正片」的真正修复：
    #   TVBox/OK影视 里 parse=1 + jx=0(或缺 jx) = 用自身 WebView 嗅探网页，
    #   抓到的第一个流就是官网 15 秒贴片广告（图1）；
    #   jx=1 才是【调用解析池】的开关，会列出「超级解析 / Web聚合 / 云…」
    #   那排名字并自动解析出正片（图2）。
    #
    #   v7.2 当时为了消掉 ⚠ 错误页，把 msg 和 jx 一起删了 —— 元凶其实
    #   只有 msg（壳把 msg 当「播放失败原因」弹出并中断解析）。删掉 jx
    #   等于把解析池开关也关了，所以后面十几轮怎么改订阅、怎么补 flag
    #   都没用：壳压根没进解析池，只是嗅探网页。
    #
    #   ★ 现在补回 jx=1，【绝不补 msg / playUrl / format】。
    #   ★ 只给官方页补；国语回放等直连走独立 return，永远不碰这里。
    # ★★ 只对「官方页」回传 flag。国语回放(微博直连)走的是 parse=0
    #    独立 return，本就不过这里；万一它取不到流落到交壳兜底，下面这层
    #    _is_official 判断也保证绝不会给它挂解析 flag —— 直连就是直连。
    if not prefix and _is_official(page):
        if OFFICIAL_ADD_FLAG:
            fl = _official_flag(page)
            if fl:
                out["flag"] = fl
        if OFFICIAL_JX:
            out["jx"] = 1

    if not OFFICIAL_CLEAN:
        # 仅供排障：打开会重现 ⚠ 错误页，默认不启用
        out.update({"playUrl": "", "format": "",
                    "msg": "已交 OK影视 壳子解析"})
    return out


def _https_parses(ps):
    """只留能拼播放页的 https 解析（兼容回退模式用）。"""
    out = []
    for name, u in ps:
        s = str(u or "").strip()
        low = s.lower()
        if not low.startswith("https://"):
            continue
        if "url=" not in low and "{url}" not in s:
            continue
        out.append((name, s))
    return out


def _official_to_shell(page, headers):
    """★★ 官方页 v7.5：拿到真实官方页后 py 零动作，原样极简交壳。

    壳自己已配好「先超级解析 → 失败自动走 https 解析」的内部解析链，
    不需要 py 回调、不需要 py 抢先探测、不需要再点一下。
    官方页不能直连，所以连 _stream_ok / 取流都不做（判定放在最前）。
    """
    hd = dict(headers or {})
    hd["User-Agent"] = _UA
    hd["Referer"] = page
    prefix = str(OFFICIAL_SNIFF_PREFIX or "").strip()

    _G["shell_turn"].pop(page, None)
    _G["official_turn"].pop(page, None)
    _G["parse_probe_log"] = []
    _G["parse_dead"] = False

    # B 备选：video:// X5 嗅探（默认不走）
    if prefix:
        _G["parse_used"] = "官方页→X5嗅探(备选)"
        return _clean_shell(page, hd, prefix)

    # 兼容回退：仅显式把 OFFICIAL_AUTO_HTTPS 改 True 才让 py 抢先探测
    # （默认 False，避免破坏壳「先超级解析、后 https」的顺序）
    if OFFICIAL_AUTO_HTTPS:
        try:
            ps, _note = _get_parses()
            cand = _https_parses(ps) if OFFICIAL_HTTPS_ONLY else list(ps or [])
            if cand:
                start, _fixed = _parse_start(cand)
                _G["parse_round"] = int(_G.get("parse_round") or 0) + 1
                if PARSE_PROBE_ALL:
                    direct, hit, logs = _probe_parse_all(cand, page, start)
                else:
                    direct, hit, logs = _probe_parse(cand, page, start)
                _G["parse_probe_log"] = logs
                if direct:
                    _G["parse_used"] = "官方页→https解析直链(兼容模式)"
                    return {"parse": 0, "url": direct, "header": hd,
                            "format": "video/mp4"}
        except Exception:
            _G["parse_probe_log"] = []

    _G["parse_used"] = "官方页→壳超级解析(顺序由壳：超级解析→https)"
    return _clean_shell(page, hd)


def _shell_return(page, head_note, headers, why):
    """非官方页交壳：同样必须零 msg，否则壳会弹 ⚠ 页中断解析。"""
    hd = dict(headers or {})
    prefix = str(OFFICIAL_SNIFF_PREFIX or "").strip()
    if prefix and _is_official(page):
        hd["User-Agent"] = _UA
        hd["Referer"] = page
        _G["parse_used"] = "壳嗅探(video://前缀)"
    return _clean_shell(page, hd, prefix if prefix and _is_official(page) else "")


def _fallback_parse(page, head_note, headers):
    """★★ v6.9 默认顺序（按用户要求）：
      ① py 直取 1080P（在本函数之外，优先级最高）
      ② 取不到 → 一律【先交 OK影视 壳子自带解析】(parse=1 + jx=1)
      ③ 壳解析播不了、返回再点同一集 → 订阅 ext.parses 全量并行尝试，
         命中直链 parse=0；没命中/全超时 → 又回 ②（壳→parses→壳 循环）

    ⚠ playerContent 一次性返回，parse=1 交出去后 py 本轮即结束，没有
      「壳失败回调 py」的机制，所以 ②③ 只能靠「同一集重试」实现。
    """
    _G["parse_used"] = ""
    _G["parse_probe_log"] = []
    if SHELL_FIRST and SHELL_PARSE_FALLBACK:
        turn = int(_G["shell_turn"].get(page, 0) or 0)
        if turn == 0 or not PARSE_ON_RETRY:
            # ② 第一次点（或关掉重试升级）：一律先壳，零探测、起播最快
            _G["shell_turn"][page] = 1 if PARSE_ON_RETRY else 0
            _G["parse_dead"] = False
            _G["parse_used"] = "壳子内置解析(默认·优先)"
            return _shell_return(
                page, head_note, headers,
                "已交 OK影视 壳子自带解析。若播不了，返回再点同一集，"
                "会改试订阅 ext.parses 全量")
        # ③ 同一集重试：这一轮改跑订阅 parses 全量；下一轮又回到壳
        _G["shell_turn"][page] = 0
        _G["parse_used"] = "重试升级：订阅parses全量尝试"
        head_note += "（壳解析未成功·本轮改试订阅parses）"
        # 不 return，落到下面的 parses 全量探测逻辑
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
                _G["shell_turn"].pop(page, None)   # 已能直连，重置为先壳
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
            #     解析，不再把解析网页地址丢给播放器（转圈/感叹号），也不停在文字页。
            dead = bool(probe_log) and all(
                ("超时/不可达" in x or "地址无效" in x or "未执行" in x)
                for x in probe_log)
            _G["parse_dead"] = dead
            if dead:
                _G["parse_used"] = "全部解析不可达"
                tip = (head_note + " → 订阅里的 %d 条解析接口暂时不可达，"
                       "已默认交 OK影视 壳子解析。逐条：%s"
                       % (n, "；".join(probe_log[:8])))
                if PARSE_DEAD_USE_SHELL and SHELL_PARSE_FALLBACK:
                    return _shell_return(page, head_note, headers, tip)
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
        return _shell_return(
            page, head_note, headers,
            "已默认交 OK影视 壳子内置解析。订阅 parses 没吐直链/"
            "全不可达/没配置都会走这里。想回到文字提示，把 "
            "SHELL_PARSE_FALLBACK 改 False")
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

    VERSION = "98直播吧 v7.5（还原真实官方页·修解析失败）"

    def getName(self):
        return "98直播吧"

    def init(self, extend=""):
        _start_warm(self)   # ★ 壳启动即异步预热推荐（后台线程，主线程零网络）
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
                # 订阅地址 / 本机订阅文件：subscribe / urls / parses_file …
                if isinstance(obj, dict):
                    subs, local_files = [], []
                    for k in ("subscribe", "subscribeUrl", "sub", "url",
                              "parses_file", "parsesFile", "configFile",
                              "config_file", "file", "path"):
                        v = str(obj.get(k) or "").strip()
                        if not v:
                            continue
                        u = _maybe_sub_url(v)
                        if u:
                            subs.append(u)
                            continue
                        low = v.lower()
                        if not low.startswith(("http://", "https://")) and \
                                (low.startswith("/") or "\\" in v or
                                 low.endswith((".json", ".txt", ".js"))):
                            local_files.append(v)
                    if local_files:
                        _G["cfg_files"] = local_files[:6]
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
        "filter": {}   # 直播分类已隐藏，不再挂它的筛选组
    }
    header = {
        "User-Agent": _UA,
        "Referer": SITE + "/"
    }

    # ------------------------------------------------------------------
    def homeContent(self, filter):
        """★ 纯静态、零网络；一级分类只输出 SHOW_CATS 白名单里的。"""
        _start_warm(self)   # 双保险：壳必调本方法，保证预热一定启动（幂等）
        result = {}
        classes = []
        for k, n, _p in _VISIBLE_CATS:
            classes.append({'type_name': n, 'type_id': k})
        result['class'] = classes
        if filter and self.config['filter']:
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        """★ 壳子预览页「更新推荐」与【NBA录像】分类栏下显示完全一致。

        直接复用 categoryContent("nba", 1) 的最终列表：近三天、国语回放
        校验、排除集锦/精华/十佳、顺序、备注全部一致，不会再混入腾讯
        原声/国语卡片。

        ★★ 分类更新 → 首页跟着更新：分类页每次成功刷新都会覆盖
        _G["nba_final"] 并把 nba_rev +1。本方法【每次都以 nba_final 为
        唯一真相】，不用自己那份旧快照短路返回，所以点一次分类刷新，
        再回首页就是新列表；同步版本号记在 home_rev，源自检可查。
        读缓存是纯内存、零网络请求，不会拖慢首页。
        ★ 冷启动：后台线程预热，主线程最多等 HOME_WARM_WAIT 秒即出推荐；
          断网/分类失败不清空已有结果。
        """
        if not HOME_SHOW_NBA:
            return {'list': []}
        items = []
        try:
            if HOME_NBA_SYNC_CAT:
                final = _G.get("nba_final")
                if final is None:
                    if HOME_WARM_ON:
                        # ★★ 启动即有推荐 + 不卡：init/homeContent 已起后台线程
                        #    跑完整 categoryContent（与分类页同一套逻辑），主线程
                        #    在这里【最多等 HOME_WARM_WAIT 秒】，绝不 12~57 秒阻塞。
                        _start_warm(self)
                        if HOME_WARM_WAIT > 0:
                            try:
                                _WARM_EVT.wait(HOME_WARM_WAIT)
                            except Exception:
                                pass
                        final = _G.get("nba_final")
                        if final is not None:
                            items = list(final)      # 后台已算完：最终一致结果
                        else:
                            # 后台还没算完（仅直连版详情页校验较慢）：用同一份
                            # 栏目页缓存【纯内存】出卡片，零网络、零等待 → 启动
                            # 即有。后台写 nba_final 后，壳刷新自动收敛为最终列表。
                            _pg = _G.get("nba_page")
                            if _pg:
                                _h, _b, _u = _pg
                                try:
                                    items = self._items(_h, _b)[:120]
                                except Exception:
                                    items = []
                    elif HOME_NBA_CACHE_ONLY:
                        items = []
                    else:
                        # 关掉预热时的应急通道：同步跑（可能慢，仅排障用）
                        r = self.categoryContent("nba", 1, False, {})
                        items = list(r.get("list") or [])
                        if _G.get("nba_final") is not None:
                            items = list(_G["nba_final"])
                else:
                    items = list(final)      # ★ 永远取分类页最新结果、零请求
                if HOME_NBA_LIMIT and HOME_NBA_LIMIT > 0:
                    items = items[:HOME_NBA_LIMIT]
            else:
                # 旧轻量模式（兼容应急）：栏目页缓存也会随分类刷新更新
                final = _G.get("nba_page")
                if final:
                    html, base, _u = final
                elif HOME_NBA_CACHE_ONLY:
                    html, base = "", ""
                else:
                    html, base = "", ""
                    for p in _CAT_FALLBACKS.get("nba", []):
                        cu = _abs(p, SITE + "/")
                        h0, f0 = _fetch(cu, ref=SITE + "/",
                                        timeout=HOME_NBA_TIMEOUT, alt=False)
                        if h0 and self._items(h0, f0 or cu):
                            html, base = h0, (f0 or cu)
                            break
                if html:
                    items = self._items(html, base)
                    if HOME_NBA_RECENT and NBA_RECENT_ON:
                        items = [x for x in items if _recent_ok(x["vod_name"])]
                    items = items[:max(HOME_NBA_LIMIT, 12)]
        except Exception:
            # 异常时保留上一次快照，避免首页突然被清空
            items = list(_G.get("home_nba") or [])
        _G["home_nba"] = items
        _G["home_rev"] = _G.get("nba_rev", 0)
        return {'list': items}

    # ------------------------------------------------------------------
    def _home(self):
        if _G["home"] is not None:
            return _G["home"]
        h, f = _fetch(SITE + "/", timeout=2, alt=False)
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
            nt = _norm(text)
            if not nt or len(nt) > 12:
                continue
            for k, name, _p in _CATS:
                if k in ("today", "live", "diag") or k in _G["cat_url"]:
                    continue
                nn = _norm(name)
                # 「足球录像」/「足球录像回放」/「NBA录像回放」都能命中；
                # 但不允许「NBA」这种短导航抢走「NBA录像」分类(会学错 URL)。
                if nn and nn in nt and len(nt) <= len(nn) + 4:
                    _G["cat_url"][k] = href
                    break

    def _items(self, html, base):
        """★ 分类页/首页的比赛卡片。

       旧版强制标题含「录像|回放|集锦|十佳|精华|全场」，把 98 分类页里
       大量只写「腾讯原声 / 腾讯国语 / 英超第N轮 …vs…」的比赛整批丢掉，
       于是足球录像比原站少一大半、NBA 只剩「国语回放」那几场。
       现在只要求「像一条比赛条目」：含日期 或 含 vs/对阵。
       """
        out, seen = [], set()
        for href, text in _links(html, base):
            t = _clean(text)
            if not t or len(t) < 6 or len(t) > 110:
                continue
            has_date = re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年|"
                                 r"\d{1,2}[-/]\d{1,2}", t)
            # 不用 vs\b：中文队名紧跟 vs（「曼联vs利物浦」）时 \b 不成立
            has_game = re.search(r"(?i)vs|对阵|\d{1,2}\s*[-:]\s*\d{1,2}", t)
            # ★ 没有日期也没有 vs 的比赛（如「英超第12轮 全场录像回放」）
            #   靠「录像/回放/全场」独立准入，避免整批漏掉。
            has_rec = re.search(r"录像|回放|全场|完整版|第[一二三四1-4]节", t)
            if not (has_date or has_game or has_rec):
                continue
            if _EP_SKIP.search(t) or href in seen or not _is98(href):
                continue
            # 「视频录像专区 / 栏目列表」这类导航词不算比赛
            if re.search(r"专区|频道|栏目|列表|排行榜|专题", t) and \
                    not (has_date or has_game):
                continue
            # 纯直播/比分链接不进录像列表（除非标题本身写了录像回放）
            if re.search(r"直播|比分", t) and not re.search(r"录像|回放|全场", t):
                continue
            # ★ 二级目录：全场精华 / 集锦 / 十佳 等一律不进列表（保留用户要求）
            if DROP_HIGHLIGHTS and _HIGHLIGHT_SKIP.search(t):
                continue
            seen.add(href)
            dm = re.search(r"\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月\d{1,2}日", t)
            # ★★ 卡片上【所有可能被壳渲染的字段都放短名】：
            #   上一版把完整原名塞进 vod_remarks，壳把它折成两行截断，
            #   看起来像「改动没生效」。现在 name/remarks 一律短名，
            #   完整原名只留在 _G["title_full"] 缓存 → 详情页标题/正文。
            _G.setdefault("title_full", {})[href] = t
            _sh = _short_title(t)
            out.append({"vod_id": _enc(href), "vod_name": _sh,
                        "vod_pic": "", "vod_remarks": _sh})
        return out

    def _guoyu_check(self, href):
        """★ 抓比赛详情页，判断有没有【国语回放】分组（微博组，py 能直取
        1080P）。腾讯国语/腾讯原声不算。返回 True / False / None(抓不到)。

        三层判据，抗源站改分组文案：
          ① 微博正文链接（最本质特征，分组改名也认得）
          ② 链接文本里的「国语回放 / 中文解说 / 微博回放」
          ③ 纯文本 [分组名]
        """
        ck = _G.setdefault("guoyu_cache", {})
        if href in ck:
            return ck[href]
        h, f = "", ""
        for attempt in range(max(GUOYU_RETRY, 0) + 1):
            try:
                # ★ 第一次就允许换备用域；失败再重试一次
                h, f = _fetch(href, ref=SITE + "/", timeout=GUOYU_TIMEOUT,
                              alt=(GUOYU_ALT or attempt > 0))
                if h:
                    break
            except Exception:
                h, f = "", ""
        if not h:
            # ★★ 不缓存 None：一次网络抖动不会把这个进程里该场永久放行，
            #     下次分类刷新会重新抓。
            return None
        ok = False
        links = _links(h, f or href)
        # ① 可直连线路：微博正文（国语回放）或 央视网页面（CCTV国语）
        for u, _inner in links:
            if _WB_POST_RE.search(u) or _is_cctv(u):
                ok = True
                break
        # ② 链接文本分组名（不再因为同一行出现「腾讯」就整条跳过）
        if not ok:
            for _u, inner in links:
                t = _clean(inner)
                if t and _GUOYU_POS.search(t) and not _GUOYU_OFF.search(t):
                    ok = True
                    break
        # ③ 纯文本 [分组名]
        if not ok:
            for mm in re.finditer(r"[\[【]\s*([^\]】]{1,12})[\]】]", h):
                g = mm.group(1)
                if (_GUOYU_POS.search(g) and "腾讯" not in g and
                        "原声" not in g):
                    ok = True
                    break
        ck[href] = ok          # 只缓存 True / False
        return ok

    def _filter_guoyu(self, items):
        """★ 只保留「有国语回放 或 有 CCTV国语」的比赛（两者都能 parse=0 直连）。

        ★★ 旧版 9 秒一到就 break，剩下条目被静默放行（连标注都没有），
        源站一慢腾讯卡就整批混进来 —— 这就是「昨天有效今天失效」的根因。
        现在：每条都尽量拿到判定；实在拿不到也不无条件放行，按标题兜底
        把明确只有官方页的卡剔掉，其余保留并标「未校验」，全程留统计。
        """
        todo = items[:GUOYU_CHECK_LIMIT]
        res, lock = {}, threading.Lock()

        def work(it):
            href = _dec(it.get("vod_id", ""))
            if not href:
                return
            try:
                v = self._guoyu_check(href)
            except Exception:
                v = None
            with lock:
                res[href] = v

        t0 = time.time()
        for i in range(0, len(todo), GUOYU_WORKERS):
            batch = todo[i:i + GUOYU_WORKERS]
            ts = [threading.Thread(target=work, args=(it,), daemon=True)
                  for it in batch]
            for t in ts:
                try:
                    t.start()
                except Exception:
                    pass
            for t in ts:
                t.join(GUOYU_TIMEOUT * (max(GUOYU_RETRY, 0) + 1) + 1)
            # 极端卡死才停；停下来也不会静默放行，下面按标题兜底
            if time.time() - t0 > GUOYU_TOTAL_TIMEOUT:
                break

        out = []
        st = {"total": len(items), "hit": 0, "no": 0,
              "fail": 0, "skip": 0, "title_drop": 0, "detail": []}
        for it in items:
            href = _dec(it.get("vod_id", ""))
            v = res.get(href) if href in res else "skip"
            if v is True:
                st["hit"] += 1
                st["detail"].append("✅ 有可直连线路(国语回放/CCTV国语)  " + it["vod_name"][:24])
                out.append(it)
                continue
            if v is False:
                st["no"] += 1
                st["detail"].append("❌ 明确无可直连线路  " + it["vod_name"][:24])
                continue
            # ★ None / "skip" / 异常：不再无条件保留
            if v is None:
                st["fail"] += 1
            else:
                st["skip"] += 1
            try:
                _full4hint = (_G.get("title_full") or {}).get(
                    _dec(str(it.get("vod_id", ""))), "")
            except Exception:
                _full4hint = ""
            hint = _title_guoyu_hint(
                _full4hint or (it.get("vod_name", "") + " " +
                               it.get("vod_remarks", "")))
            if hint is False:
                st["title_drop"] += 1
                st["detail"].append("❌ 抓不到但标题是官方页  " +
                                    it["vod_name"][:26])
                continue
            it = dict(it)
            it["vod_remarks"] = (str(it.get("vod_remarks", "")) +
                                 " · 未校验")[:40]
            st["detail"].append("⚠ 抓不到/超时，保守保留  " + it["vod_name"][:26])
            out.append(it)
        _G["guoyu_stat"] = st
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
            # ★ 「今日视频」已不显示；旧缓存仍请求 today / 未知 tid 时
            #   回落到足球录像，既不会白屏，也不会把隐藏内容偷偷显示回来。
            if tid not in set(SHOW_CATS):
                tid = _FALLBACK_TID

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
            # ★★ 分类 URL：导航学到的首选 + 兜底路径逐个试，取条目最多的。
            #    旧版只试一个硬猜路径，抓不到就悄悄退回首页，于是分类里
            #    显示的是首页那几场比赛 → 「比原网站少了很多」的主因之一。
            cands = []
            u0 = _G["cat_url"].get(tid)
            if u0:
                cands.append(u0)
            for p in _CAT_FALLBACKS.get(tid, []):
                cu = _abs(p, final or SITE + "/")
                if cu not in cands:
                    cands.append(cu)
            best_html, best_final, best_url, best_n = "", "", "", -1
            for cu in cands[:2]:
                h2, f2 = _fetch(cu, ref=final or SITE + "/", timeout=3, alt=False)
                if not h2:
                    continue
                n2 = len(self._items(h2, f2 or cu))
                if n2 > best_n:
                    best_html, best_final, best_url, best_n = h2, (f2 or cu), cu, n2
                if n2 >= 12:        # 够多就不再试后面的，省时间
                    break
                # ★★ 不再为「推荐页」提前停：首页与分类页必须试用同一批
                #    候选 URL、取同一份「条目最多」的栏目页，差一次 break
                #    就会让两页内容不一致。
            url = u0 or ""
            if best_html:
                html, final = best_html, best_final
                url = _canon_cat_url(best_url, html, final)
                _G["cat_url"][tid] = url
                # ★ 点过 NBA 分类后，「更新推荐」直接复用这份栏目页，零网络。
                if tid == "nba" and pg == 1:
                    _G["nba_page"] = (html, final, url)

            # ★★ 分页：旧版第一页 pagecount 恒为 1，壳根本不翻页，
            #    只见第一页 → 足球录像比原站少很多。现在支持逐页翻到底。
            if pg > 1:
                pu = _page_url(url or final, pg)
                if pu:
                    hp, fp = _fetch(pu, ref=final or SITE + "/", timeout=5)
                    if hp:
                        html, final = hp, (fp or pu)
                else:
                    for _ in range(min(pg - 1, 8)):
                        nx = _next_page(html, final)
                        if not nx:
                            break
                        h3, f3 = _fetch(nx, ref=final, timeout=5)
                        if not h3:
                            break
                        html, final = h3, (f3 or nx)
            items = self._items(html, final)
            # ★★ 删掉「按分类名二次过滤」：比赛标题里通常没有「足球 / NBA」
            #    字样，栏目页本身就是该项目录像，不必再按标题筛一遍。

            # ★★ NBA：先按「近三天(含当天)」砍掉旧比赛，再做国语回放校验。
            #    顺序很关键 —— 要抓详情页的条目从几十条降到几条，分类页变快。
            recent_applied = False
            if NBA_RECENT_ON and tid in RECENT_ONLY_CATS:
                recent_applied = True
                items = [x for x in items if _recent_ok(x["vod_name"])]

            # ★★ NBA 只保留有「国语回放」的比赛（腾讯国语/原声解不了）
            if NBA_ONLY_GUOYU and tid in GUOYU_ONLY_CATS:
                items = self._filter_guoyu(items)

            # ★★ 真实总页数：从数字页码 / list_N_<n>.html / 「共N页」读，
            #    不再只靠「有没有下一页」把 pagecount 猜成 2。
            mx = _max_page(html, final)
            more = bool(_next_page(html, final) or
                        _page_url(url or final, pg + 1))
            if mx > 1:
                # 页面自带数字页码 → 直接给真实总页数；否则「有下一页」
                # 会让 pagecount 每翻一页 +1，一直空翻到上限 30。
                pc = mx
            else:
                pc = pg + 1 if more else pg
            # 近三天的比赛都在栏目第一页（最新在最前）；锁 pagecount=1，
            # 壳不再翻页，也不再为第 2 页重复抓一遍详情 → 这是提速主因。
            result['pagecount'] = 1 if recent_applied else min(max(pc, pg), 30)
            result.update({'list': items[:120],
                           'limit': max(len(items), 24),
                           'total': max(len(items), 24)})
            # ★ 「更新推荐」逐条复用这份最终列表（含国语回放校验结果），
            #   保证两边完全一致；点过分类后首页零请求。
            # ★★ 每次分类成功刷新都覆盖并 +1 → 首页下次打开必然跟着更新。
            #   只有走到这里(栏目页抓到、整套过滤跑完)才算有效刷新；
            #   断网/异常走 except，不动版本号也不清首页。
            if tid == "nba" and pg == 1 and best_html:
                _G["nba_final"] = list(result["list"])
                _G["nba_rev"] = _G.get("nba_rev", 0) + 1
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
            # ★ 三级目录：全场精华 / 全场集锦 / 精彩十佳球 一律不进选集
            if DROP_HIGHLIGHTS and _HIGHLIGHT_SKIP.search(t):
                continue
            m = re.match(r"^\s*[\[【(（]([^\]】)）]{1,12})[\]】)）]", t)
            if not m:
                continue
            g = m.group(1).strip()[:12]
            name = re.sub(r"^\s*[\[【(（][^\]】)）]{1,12}[\]】)）]\s*", "", t)
            short = re.search(r"第[一二三四1-4]节\s*录像|全场录像回放|"
                              r"全场回放|加时|完整版|录像回放", name)
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
                     "★ 播放页分组排序: " +
                        ((("距今>=%d天 → 腾讯国语/腾讯原声/国语回放；"
                           "距今<%d天 顺序不变(国语回放优先)") %
                          (OLD_SORT_AFTER_DAYS, OLD_SORT_AFTER_DAYS))
                         if OLD_SORT_ON else "全部按原顺序"),
                     "  ★ 只管播放页顺序；分类/推荐显示仍按 NBA_RECENT_DAYS=%d"
                     % NBA_RECENT_DAYS,
                     "  日期解析不出 → 保守不改；其余分组保持原相对顺序",
                     "★ 卡片标题: " +
                        ("精简v2：name/备注 都是短名，完整原名只在详情页"
                         if SHORT_TITLE else "完整原名"),
                     "一级分类: %d 个（%s）" %
                        (len(_VISIBLE_CATS),
                         " / ".join(n for _k, n, _p in _VISIBLE_CATS)),
                     "已隐藏: %d 个（红框分类 + 直播 + 源自检）；" %
                        (len(_CATS) - len(_VISIBLE_CATS)),
                     "  想加回：改文件顶部 SHOW_CATS 列表即可",
                     "  源自检诊断页仍保留（旧缓存点进去可用），只是不在分类栏",
                     "二级/三级目录过滤集锦·精华·十佳: " +
                        ("开启 ✅" if DROP_HIGHLIGHTS else "关闭(保留集锦)"),
                     "  保留：全场录像回放 / 第X节录像 / 全场回放",
                     "  丢弃：全场精华 / 全场集锦 / 精彩十佳球 等",
                     "★ NBA 近三天过滤: " +
                        ("开启 ✅ (%d 天含当天，分类只留最新，pagecount=1)"
                         % NBA_RECENT_DAYS if NBA_RECENT_ON else "关闭"),
                     "  无日期条目: " +
                        ("保守保留" if NBA_RECENT_KEEP_NODATE else "不保留"),
                     "  只作用于: " + ", ".join(sorted(RECENT_ONLY_CATS)),
                     "  条目少了 → 国语回放校验只需抓几条详情，分类页变快",
                     "★ 预览页「更新推荐」: " +
                        (("与 NBA录像 分类完全一致 ✅ (近三天+国语回放校验)" if
                          HOME_NBA_SYNC_CAT else "旧轻量模式(会混腾讯卡)")
                         if HOME_SHOW_NBA else "关闭(空列表)"),
                     "  ★ 不再混入腾讯原声/腾讯国语（口径与分类页相同）",
                     "  纯缓存零网络: " +
                        ("开(只在点过分类后显示)" if HOME_NBA_CACHE_ONLY
                         else "关(冷启动自己算一遍)") +
                        " / 条数上限: " +
                        ("跟随分类页" if not HOME_NBA_LIMIT
                         else str(HOME_NBA_LIMIT)),
                     "  ★ 分类刷新次数: %d / 首页已同步到第 %d 次 %s" %
                        (_G.get("nba_rev", 0), _G.get("home_rev", -1),
                         "✅ 已同步" if
                         _G.get("home_rev", -1) >= _G.get("nba_rev", 0)
                         else "⏳ 回首页即自动同步"),
                     "  ★ 分类更新后首页会跟着变（每次以分类最终列表为准）",
                     "  ★ 首页/分类试用同一批栏目候选、取同一份页面(无抓到即停)",
                     "  分类页最终列表缓存: %d 条 / 已缓存推荐: %d 条" %
                        (len(_G["nba_final"] or [])
                         if _G["nba_final"] is not None else 0,
                         len(_G["home_nba"] or [])
                         if _G["home_nba"] is not None else 0),
                     "首页分类: homeContent 零网络请求 / 无 __init__", "",
                     "【微博取流配置】",
                     "WB_COOKIE: " + ("已填 ✅" if WB_COOKIE else "未填 ❌"),
                     "", "【解析来源 = 订阅 json 的顶层 parses 独立段】",
                     "  ★ 壳解析池读顶层 parses；site.ext 里不放 parses",
                     "  ★ 解析项数量由订阅顶层 parses 段决定（py 不内置）",
                     "  ★ 国语回放/明文直链 = parse=0 直连，绝不挂解析 flag",
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
                     "★★ 兜底顺序: py直取 → 壳子自带解析 → (同一集重试)" +
                        "订阅ext.parses全量 → 回壳",
                     "  注: parse=1 一次性返回，壳失败无回调；" +
                        "「先壳再parses」靠再点同一集实现",
                     "SHELL_FIRST: " + ("开(一律先交壳自带解析)"
                                        if SHELL_FIRST else "关(先试订阅parses)"),
                     "PARSE_ON_RETRY: " + ("开(重试才试订阅parses)"
                                           if PARSE_ON_RETRY else "关(永远只用壳)"),
                     "★★ 官方视频: py 零动作，直接极简交壳",
                     "   顺序由壳负责：超级解析 → 失败自动走 https 解析",
                     "   不试直连 / 不取流 / 不探测 / 不用再点一下",
                     "★★ OFFICIAL_AUTO_HTTPS: " +
                        ("开(兼容回退,py抢先探测,不推荐)" if OFFICIAL_AUTO_HTTPS
                         else "关【默认·顺序完全交给壳】"),
                     "OFFICIAL_HTTPS_ONLY: " +
                        ("开" if OFFICIAL_HTTPS_ONLY else "关") +
                        " (仅兼容回退时生效)",
                     "★★ OFFICIAL_CLEAN: " +
                        ("开【交壳零msg·修掉⚠错误页】" if OFFICIAL_CLEAN
                         else "关(会重现⚠页,不建议)"),
                     "★★ OFFICIAL_JX: " +
                        ("开【parse=1 + jx=1 真正调用壳解析池】" if OFFICIAL_JX
                         else "关(只嗅探网页→会抓到官网贴片广告)"),
                     "  注: msg 才是 ⚠ 错误页元凶，永远不补；"
                        "国语回放直连不挂 jx/flag",
                     "OFFICIAL_ADD_FLAG: " +
                        ("开(仅非精简模式生效)" if OFFICIAL_ADD_FLAG
                         else "关"),
                     "OFFICIAL_SNIFF_PREFIX: " +
                        (repr(OFFICIAL_SNIFF_PREFIX) + " (X5 嗅探备选)"
                         if OFFICIAL_SNIFF_PREFIX else "留空(走壳解析池)"),
                     "OFFICIAL_PAGE_HINT: " +
                        ("开(附侧栏手选提示)" if OFFICIAL_PAGE_HINT
                         else "关(msg 极简)"),
                     "★ 默认兜底: " + ("OK影视 壳子内置解析(parse=1+jx=1)"
                                      if SHELL_PARSE_FALLBACK else "可读文字提示"),
                     "PARSE_DEAD_USE_SHELL: " + ("开(全不可达交壳解析)"
                                                 if PARSE_DEAD_USE_SHELL
                                                 else "关(全不可达给明确提示)"),
                     "PARSE_ADDR_FALLBACK: " + ("开(无直链时轮换解析地址)"
                                                if PARSE_ADDR_FALLBACK
                                                else "关(无直链直接交壳)"),
                     "壳子解析兜底: " + ("开启" if SHELL_PARSE_FALLBACK else "关闭"),
                     "本集下一轮: " + ("订阅parses全量"
                                     if any(v == 1 for v in
                                            (_G["shell_turn"] or {}).values())
                                     else "壳子自带解析"),
                     "上次解析可达性: " + ("全部不可达 ⚠ 已自动交壳解析"
                                        if _G["parse_dead"] else "正常/尚未触发"),
                     "本次兜底使用: " + (_G["parse_used"] or "（尚未触发）"),
                     "第 %s 轮 / 下次起点编号 %s" %
                        (_G["parse_round"], _G["parse_cursor"]),
                     ""]
            # ★★ 国语回放筛选统计：真机看这里就知道「失效」是哪一类
            _gs = _G.get("guoyu_stat") or {}
            if _gs:
                lines += [
                    "", "★★【可直连线路筛选(国语回放 / CCTV国语) · 本轮校验统计】",
                    "  共 %d 场 / ✅命中 %d / ❌明确无 %d / ⚠抓不到 %d / "
                    "⏳超时 %d / 标题兜底剔除 %d" %
                    (_gs.get("total", 0), _gs.get("hit", 0),
                     _gs.get("no", 0), _gs.get("fail", 0),
                     _gs.get("skip", 0), _gs.get("title_drop", 0)),
                    "  开关: NBA_ONLY_GUOYU=%s / 备用域=%s / 重试=%d / "
                    "单条%ds / 硬上限%ds" %
                    (NBA_ONLY_GUOYU, GUOYU_ALT, GUOYU_RETRY,
                     GUOYU_TIMEOUT, GUOYU_TOTAL_TIMEOUT),
                    "  ★ 抓不到≠放行：明确只有腾讯/爱奇艺/优酷/咪咕的标题会被剔除",
                    "  ★ 失败不缓存：下次分类刷新会重抓，一次抖动不会永久放行",
                    "  【逐条判定（末 12 条）】"]
                lines += ["  " + x for x in
                          (_gs.get("detail") or ["（暂无）"])[-12:]]
            else:
                lines += ["", "★★【国语回放筛选】本轮尚未触发",
                          "  （进一次 NBA录像 分类，再回来点本页即可看到统计）"]
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
            lines += ["", "【★★ 上一次官方视频交壳链路】"
                      "（点一节「腾讯国语/腾讯原声」后再回来）"]
            _tr = _G.get("official_trace") or []
            lines += ["  " + x for x in (_tr or ["（暂无，去点一节官方线路）"])[-12:]]
            lines += ["  判定：最后一行的「最终交壳」必须是 v.qq.com / "
                      "iqiyi.com 等官方域名；",
                      "  若是 m.98zb.com 中转页，壳必然报「播放地址解析失败」。"]
            lines += ["", "【上一次真实取流日志】（点一节录像后再回来）"]
            lines += ["  " + x for x in (_G["wb_log"] or ["（暂无）"])[-14:]]
            lines += ["", "【★ 配置与排障（按真机验证结果更新）】",
                      "订阅填本机文件路径；api = ./py/98直播.py",
                      "  （中文名 + 相对路径在本版已验证可用，勿凭通用经验改动）",
                      "★ 源消失/没分类时先查：订阅是否被自动更新覆盖、",
                      "  存储权限、JSON 合法性、壳缓存；先看源名字在不在，",
                      "  再判断是配置问题还是代码问题。",
                      "", "【★ 解析只在订阅【顶层 parses 独立段】】",
                      "py 已不内置任何解析，site.ext 里也不放 parses；换解析改订阅。",
                      "", "【★ 官方视频（腾讯国语/腾讯原声等）】",
                      "官方页不能直连 → py 不试直连、不取流、不探测、不重试。",
                      "★ 98 若给中转页：先从 iframe/JS/?url=/302 抠出真实",
                      "  v.qq.com 等官方页再交壳（否则壳报解析失败）。",
                      "★ 交壳字段 parse=1 + jx=1 + flag + url + header，零 msg：",
                      "  jx=1 是调用解析池的开关（缺了只会嗅探网页、抓到贴片广告）；",
                      "  msg 会被壳当播放失败原因弹 ⚠ 页并中断解析，永不补。",
                      "顺序由壳执行：先【超级解析】，失败后自动走【https 解析】。",
                      "", "【★ 其余线路（微博国语回放等）】",
                      "py 直取 1080P 直链 parse=0；直连绝不挂 jx / flag。",
                      "取不到流 → 交壳兜底（仍不带 jx/flag），不依赖 ext.parses。",
                      "", "清一次壳缓存 → 重启 OK影视"]
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
        _full = ((_G.get("title_full") or {}).get(url) or
                 (_G.get("title_full") or {}).get(_dec(vid)))
        title = _full or (_clean(mt.group(1)) if mt else url)

        eps = self._episodes(html, final or url) if html else {}
        if eps:
            # ★ 默认「最近三天」显式顺序（稳定排序，名单外保持原相对顺序）
            ordered = _reorder_groups(eps.items(), NEAR_SORT_ORDER)
            # ★ 距今 >= OLD_SORT_AFTER_DAYS 天 → 换成「三天以前」顺序
            _days = _game_days(title)
            _is_old = (OLD_SORT_ON and _days is not None and
                       _days >= OLD_SORT_AFTER_DAYS)
            if _is_old:
                ordered = sorted(ordered,
                                 key=lambda kv: _old_group_rank(kv[0]))
            shows, urls = [], []
            for g, lst in ordered:
                shows.append(g)
                urls.append("#".join("%s$%s" % (n, _enc(u)) for n, u in lst))
            wb_n = sum(1 for v in eps.values() for _n, u in v if _is_weibo(u))
            _head = ("【本场分节】%d 个线路 / %d 集（微博 %d 集）。"
                     % (len(eps), sum(len(v) for v in eps.values()), wb_n))
            desc = _head + (
                (("【三天以前(含当天)/距今>=%d天】CCTV国语 → 腾讯国语 → "
                   "腾讯原声 → 国语回放，优先央视超清直连。" %
                   OLD_SORT_AFTER_DAYS)
                 if _is_old else
                 ("【最近%d天含当天】国语回放 → CCTV国语 → 腾讯国语 → 腾讯原声；"
                  "国语回放 1080P 直连；CCTV国语 自动选官网超清最高档"
                  "（源最高 720P）；腾讯等官方页由订阅顶层 parses 解析。" %
                  OLD_SORT_AFTER_DAYS)))
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
            "vod_director": "",
            "vod_content": (("完整比赛名：" + _full + "\n\n") if _full
                            else "") + desc,
            "vod_play_from": play_from, "vod_play_url": play_url}]}

    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            kw = str(key or "").strip()
            if kw:
                html, final = self._home()
                _items_all = self._items(html, final)
                _fulls = _G.get("title_full") or {}
                videos = [x for x in _items_all
                          if kw in x['vod_name'] or
                          kw in _fulls.get(_dec(x['vod_id']), '')][:40]
        except Exception:
            videos = []
        result = {'list': videos}
        return result

    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        """★ 官方视频(腾讯国语/腾讯原声等)：最优先、py 零动作。
           官方页不能直连 → 不试直连、不取流、不探测，原样极简交壳
           (parse=1 + url + header，零 msg)。壳自己按「超级解析 →
           失败自动走 https 解析」完成，顺序由壳决定。

        ★ 其余页面（微博国语回放等）：py 直取 1080P 直链 parse=0；
           取不到时 ② 一律先交壳解析 ③ 同一集重试才试订阅 parses。
        """
        headers = {'User-Agent': _UA, 'Referer': SITE + '/'}
        target = ''
        try:
            raw = str(id or "").strip()
            target = _dec(raw)
            if not target.startswith("http"):
                target = _abs(target, SITE + "/")

            # ★★ CCTV国语（央视网）：py 内取【超清】2000 档 → parse=0 直连。
            #    不进解析池、不挂 flag/jx，与「国语回放」逐字段同形态。
            #    判定必须放在 _is_official 之前：_OFFICIAL_HOSTS 含 cctv，
            #    否则央视页会被当成官方页交壳解析。
            if CCTV_DIRECT_ON and (_is_cctv(target) or
                                   _CCTV_GROUP.search(str(flag or ""))):
                _hd = {'User-Agent': _UA, 'Referer': CCTV_REF,
                       'Origin': 'https://sports.cctv.com',
                       'Accept': '*/*'}
                _best, _lg = _cctv_resolve(target)
                _G["cctv_log"] = _lg
                if _best:
                    _G["official_trace"] = [
                        "CCTV国语: " + str(target)[:150],
                        "★ 最终: parse=0 直连央视超清(" + CCTV_SUPER_BR +
                        "档) " + str(_best)[:150]] + ["  " + x for x in _lg[-4:]]
                    # ★ 恢复 format：回到真机「能播」那一版的字段形态。
                    #   上一轮去掉它是基于推测，与「完全不能播」叠加成新变量，
                    #   先回到已验证基线，解码问题等能播后再单独收敛。
                    return {"parse": 0, "playUrl": "", "url": _best,
                            "jx": 0, "header": _hd,
                            "format": "application/x-mpegURL"}
                # 连 pid 都抠不到：极简交壳（parse=1 + jx=1 + flag=cctv）。
                #   绝不把央视网页当媒体给 parse=0 —— 那会静默黑屏 00:00。
                _G["official_trace"] = ["CCTV国语取流失败，回退壳解析"] + _lg[-4:]
                return {"parse": 1, "playUrl": "", "url": target,
                        "jx": 1, "flag": "cctv", "header": _hd}

            # ★★ 官方视频（腾讯国语/腾讯原声等）：第一动作就是极简交壳。
            #    官方页不能直连，不试 _stream_ok、不取流、不拼解析地址。
            #    壳已配好「先超级解析 → 失败自动走 https 解析」，py 不介入。
            if _is_official(target):
                _G["official_trace"] = ["直接官方页: " + target[:160],
                                        "★ 最终交壳: " + target[:160]]
                return _official_to_shell(target, headers)

            # ★★ 分组是「腾讯国语/腾讯原声…」但链接是包装页/中转页时，
            #    先还原出真实官方页再交壳。否则壳拿到 98 站域名不认，
            #    超级解析 + https 解析全跑完仍报「播放地址解析失败」。
            if _OFFICIAL_GROUP.search(str(flag or "")) and not _is_weibo(target):
                return _resolve_official(target, headers)

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
                        # ★ 中转页里若嵌的是腾讯/爱奇艺官方页，抽出真实
                        #   官方页再交壳；不要把 98 中转页丢给壳解析。
                        if _is_official(href):
                            return _official_to_shell(href, headers)
                    # ★ 双保险：整页（含 iframe/JS/?url=）也扫一遍官方页，
                    #   不依赖 <a href>，避免把 98 中转页丢给壳。
                    for real in _official_urls(h + "\n" + str(f or ""), page):
                        _G["official_trace"] = [
                            "中转页(双保险): " + str(target)[:150],
                            "★ 还原到: " + real[:160]]
                        return _official_to_shell(real, headers)
                    m = _MEDIA_RE.search(_unesc(h))
                    if m:
                        return {"parse": 0, "playUrl": "", "url": m.group(0),
                                "jx": 0, "header": headers, "format": 'video/mp4'}
                if _is_official(page):
                    return _official_to_shell(page, headers)
                _G["official_trace"] = [
                    "中转页未抠到官方页: " + str(target)[:150],
                    "fetch final: " + str(f or "无")[:120],
                    "⚠ 交壳的是中转页 —— 壳很可能报解析失败，请把这几行发来"]
                return _fallback_parse(
                    page, "98中转页未取到内联/微博直链",
                    self._fb_headers(page, headers))

            # ---- 其它第三方页面：仍按「先壳 → 重试才试订阅 parses」顺序 ----
            #    官方页已在最前面纯交壳，不会走到这里。
            return _fallback_parse(
                target, "第三方页面",
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
