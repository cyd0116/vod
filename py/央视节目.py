"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '中央电视台',
  lang: 'hipy'
})
"""

#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..') 
from base.spider import Spider
import json
import time
import base64
import re
from urllib import request, parse
import urllib
import urllib.request
import time

# ===== 央视频「电视栏目」50 栏目离线兜底快照 (lid, 栏目名, 栏目cid, 期次备注) =====
# 注意: 这不是官网数据源, 仅当 program 接口彻底不可用时才用, 见上方说明。
# 来源: 日志category(program_library)返回的完整栏目清单, 与别人"电视栏目"分类一致。
# vod_id三段式: library~~~<lid>~~~<cid>; detailContent用 lid 取全部期次(~~~cid)。
_YSP_COLUMNS = [
	("10492","新闻联播","skmna7n7ptliakk","2026/9/17期"),
	("10151","焦点访谈","r8ap1hpwf7licpc","2026/9/17期"),
	("10031","今日说法","sxcrcv4u3ulhveo","2026/9/17期"),
	("10028","百家讲坛","rc2u01hhflli74n","2026/9/17期"),
    ("10469","味道","02lfcgumxam3qmm","2026/9/28期"),
    ("10013","健康之路","psxk7xeop4m89a5","2026/10/01期"),
	("10526","新闻1+1","96ig3h0e81lijcn","2026/9/17期"),
	("10136","今日亚洲","712anafdu5li58w","2026/9/15期"),
	("10747","新闻直播间","a1v7a9etuhlfra1","2026/9/17期"),
	("10050","走遍中国","rq6d67e7bxli4xs","2026/9/16期"),
	("10819","2026美加墨世界杯","f5tsldorccggid3","2026/7/20期"),
	("10016","天下足球","rpahzcz795kzvvp","2026/9/7期"),
	("10022","对话","8p2ernljp5kwd5g","2026/9/5期"),
	("10029","今日关注","dhbnqvwo2bliiym","2026/9/17期"),
	("10111","鲁健访谈","5nuax203bul6hgm","2026/9/11期"),
	("10205","军事纪实","hoqwpuzr4elhjnw","2026/9/16期"),
	("10224","中国经济大讲堂","ijeucmc76xlafz8","2026/9/13期"),
	("10366","生命线","qix0uf2ltm77fzb","2025/12/13期"),
	("10490","新闻调查","r1m5gjkggjl99u4","2026/9/12期"),
	("10497","面对面","sz7563ljzyky6le","2026/9/6期"),
	("10501","法治在线","hu5q09a0ijlhvpt","2026/9/17期"),
	("10507","每周质量报告","8q2jq68cnwlafsd","2026/9/13期"),
	("10508","新闻周刊","w7rzb2vw7gkwevi","2026/9/5期"),
	("10509","世界周刊","q8unmwa474lb7g8","2026/9/13期"),
	("10514","北京2022","yduyns88fwrylxn","2023/3/16期"),
	("10567","《守护明天》第四季","7189hznzc385fba","10期全"),
	("10577","国防故事","rx9ve1gbrwlhjch","2026/9/16期"),
	("10624","秘密大改造","sfe3yubrir6ag46","12期全"),
	("10625","北京2022冬奥会","8xiostygjc6b4ua","31期全"),
	("10626","《故事里的中国》第三季","ewuii0wdekbklfu","2022/5/8期"),
	("10635","国家宝藏","34ikzq21lf4erfa","10期全"),
	("10640","五环纪事","d10hdn0n5vet6it","2024/6/5期"),
	("10645","2021-2022赛季CBA联赛","to7adonhbsay2vc","308期全"),
	("10646","国家宝藏·展演季","5mdupnecx9536p0","11期全"),
	("10647","好戏连连看","d1xsynagjonydtb","2022/12/30期"),
	("10649","奥林匹克人","7vhvezxtx06obrp","2022/2/1期"),
	("10651","2021“汉语桥”","ubteijdcohaoqu5","2021/11/2期"),
	("10654","奥秘无穷","was92fkdc2cswrd","2026/3/29期"),
	("10655","2021/22赛季德甲联赛","a8si2aitz47kbbi","2022/2/13期"),
	("10656","艺术里的奥林匹克","970h8tnbxnlb697","2026/9/13期"),
	("10657","《守护明天》第五季","605dsp6gf43belo","10期全"),
	("10658","2021年斯诺克英国锦标赛","dcurvfrxhg7jt9v","33期全"),
	("10659","2021/22赛季意甲联赛","b3454gtlvucakh0","36期全"),
	("10660","2021/22赛季法甲联赛","kg5uthtb5r7k75h","2022/2/7期"),
	("10661","《秘密大改造》第二季","gy1zafuvmc497nv",""),
	("10674","中国电影报道","cvc707ty7kk2hi6","2026/8/19期"),
	("10682","乡村振兴中国行","hj1zafi09ebfckm","2026/3/6期"),
	("10685","高端访谈","7i1tvivq49l7f6b","2026/9/11期"),
	("10725","健康中国","srijdlkrfzkzlvp","2026/9/6期"),
	("10780","《中国国宝大会》第四季","30ambc8qtyagf8g","2026/2/14期"),
]
# ★修复④: 上表第4列是旧版写死的期次日期(如 2026/9/17期), 曾直接当作卡片 vod_remarks,
#   导致所有栏目显示同一个固定日期。现在卡片日期一律由 program 接口动态返回, 这里把
#   静态表的备注统一清空, 仅保留 (lid, name, cid) 供历史收藏的 library~~~ id 兼容解析。
_YSP_COLUMNS = [(lid, name, cid, '') for lid, name, cid, rem in _YSP_COLUMNS]
# lid -> (name,cid,remark)
_YSP_COLUMNS_MAP = {lid:(name,cid,rem) for lid,name,cid,rem in _YSP_COLUMNS}

# ===== 央视频 search: 剧名->vid 运行时映射 (纯Python, 无第三方依赖) =====
class _YspPB:
	__slots__ = ("d","o")
	def __init__(self, d, o=0):
		self.d=d; self.o=o
	def varint(self):
		v=0; sh=0
		while self.o < len(self.d):
			b=self.d[self.o]; self.o+=1
			v |= (b & 0x7f) << sh
			if not (b & 0x80): return v
			sh += 7
		return v
	def read(self):
		out=[]
		while self.o < len(self.d):
			tag=self.varint(); fnum=tag>>3; wt=tag&7
			if wt==0: val=self.varint()
			elif wt==2:
				ln=self.varint(); val=self.d[self.o:self.o+ln]; self.o+=ln
			elif wt==1: val=self.d[self.o:self.o+8]; self.o+=8
			elif wt==5: val=self.d[self.o:self.o+4]; self.o+=4
			else: break
			out.append((fnum,wt,val))
		return out

_YSP_SEARCH = "https://csapi.yangshipin.cn/voapi/omsotm/v2/search"
_YSP_HDRS = {"yspappid":"539073109","platform":"109","app-platform":"m","app-version":"1.0.0","User-Agent":"Mozilla/5.0"}

def _ysp_s(b):
	try: return b.decode("utf-8","ignore")
	except Exception: return ""

def _ysp_vid_of(av):
	vid=None; ep=None
	for fn,wt,val in av:
		if wt==2 and isinstance(val,bytes):
			if fn==6: vid=_ysp_s(val)
			elif fn==1:
				for f2,w2,v2 in _YspPB(val).read():
					if w2==2: vid=_ysp_s(v2)
					elif w2==0: ep=v2
			elif fn==2: ep=_ysp_s(val)
		elif wt==0 and fn==9: ep=val
	return vid, ep

def _ysp_search(title, size=20):
	import urllib.parse, ssl
	url="%s?type=0&query=%s&page=1&size=%d" % (_YSP_SEARCH, urllib.parse.quote(title), size)
	req=urllib.request.Request(url, headers=_YSP_HDRS)
	ctx=ssl._create_unverified_context()
	d=urllib.request.urlopen(req, timeout=20, context=ctx).read()
	data=None
	for fn,wt,val in _YspPB(d).read():
		if fn==2 and wt==2: data=_YspPB(val).read()
	if not data: return []
	albums=[]
	for fn,wt,val in data:
		if fn!=1 or wt!=2: continue
		for f3,w3,v3 in _YspPB(val).read():
			if f3!=3 or w3!=2: continue
			a=_YspPB(v3).read()
			alb={"cid":"","title":"","descr":"","vids":[]}
			for f4,w4,v4 in a:
				if f4==3 and w4==2: alb["cid"]=_ysp_s(v4)
				elif f4==4 and w4==2: alb["title"]=_ysp_s(v4)
				elif f4==6 and w4==2: alb["descr"]=_ysp_s(v4)
				# 专辑海报横图(fn17): 央视频搜索protobuf返回的封面URL(如
				#   https://jietufengmian.yangshipin.cn/...create_new_pic_hz/xxx.jpg/1080?imageMogr2/format/webp)
				#   用于搜索结果 vod_pic 与 prog四段式第4段cover, 使搜索结果图片正常显示。
				elif f4==17 and w4==2 and _ysp_s(v4).startswith('http'): alb["cover"]=_ysp_s(v4)
				elif f4==10 and w4==2:
					vid,ep=_ysp_vid_of(_YspPB(v4).read())
					alb["vids"].append({"ep":ep,"vid":vid})
			if alb.get("cid"): albums.append(alb)
	return albums

# ============ 央视频 program 分类接口 (签名公式已用官网 HAR 真实 body 验证) ============
# ★本轮依据: 用户从 https://yangshipin.cn/resource/pool 导出的 HAR(95 条请求)。
#   逐条对照发现旧 py 与官网 PC 站有 4 处硬差异, 这是"电视栏目找不到数据/节目不全"
#   的直接原因 —— 请求根本没打到官网同一个端点:
#     接口路径  官网 /voapi/omsot/media/v2/program    旧py /voapi/omsotm/... (多一个 m)
#     yspappid  官网 519748109                       旧py 539073109 (移动端)
#     Referer   官网 https://yangshipin.cn/           旧py https://m.yangshipin.cn/static/m/pool
#     Origin    官网 https://yangshipin.cn            旧py https://m.yangshipin.cn
#   filterValue 官网实测为 d11=program_library&itype=-1&sort=6, 与 _ysp_build_fv 输出一致 ✔
#   yspsdkinput 用 HAR 的 body {"filterValue":"...","page":7,"pageSizeT":1} 重算 md5,
#   得 d3e8afab4bff21eacf38a521fdbeb77e, 与官网请求头逐字相同 -> 签名算法完全正确 ✔
#   yspsdksign 格式 md5(raw)-<input>-<guid>-<seqid>-<request-id> 亦与旧实现一致 ✔
# ★双配置候选: 优先用官网 PC 配置(A); 若服务端对该配置签名校验不通过则回退旧移动端
#   配置(B), 保住纪录片/特别节目原有可用链路。命中即停, 结果写进诊断。
import hashlib as _hl, random as _rd
_YSP_TOKEN_URL  = "https://h5access.yangshipin.cn/web/open/token"
_YSP_PGUID      = "mu1k3hl8_8zhsvo0vhwn"
_YSP_PCOOKIE    = ("guid=%s; versionName=99.99.99; versionCode=999999; vplatform=109; platformVersion=Chrome; deviceModel=108; newLogin=1; pc_version=1.1.16; _abfpc=951791353206c47aa9fc22c73c8c99618fd54a77_2.0; cna=16fbd097dc393531d33a81a1a558e99b" % _YSP_PGUID)
_YSP_PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0")
_YSP_M_UA  = ("Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
              "Chrome/91.0.4472.120 Mobile Safari/537.36")
# (标签, 接口URL, yspappid, Referer, Origin, UA, 签名domain, 签名appid)
# ⚠签名 raw 里的 domain/appid 无法从 HAR 反推(响应体已清理, 缺 token 原文), 属推断项。
#   故加一条 'pc_mix': 端点与请求头用官网 PC 值, 但签名 raw 沿用原移动端 SDK 常量,
#   覆盖"官网换了端点却仍用旧 SDK 签名串"这种情况。三者按顺序命中即停, 只在失败时
#   才多发一次请求, 正常路径仍是单次请求。
_YSP_API_CFG = (
    ('pc',  'https://csapi.yangshipin.cn/voapi/omsot/media/v2/program',
     '519748109', 'https://yangshipin.cn/', 'https://yangshipin.cn',
     _YSP_PC_UA, 'yangshipin.cn', '519748109'),
    ('pc_mix', 'https://csapi.yangshipin.cn/voapi/omsot/media/v2/program',
     '519748109', 'https://yangshipin.cn/', 'https://yangshipin.cn',
     _YSP_PC_UA, 'm.yangshipin.cn', '539073109'),
    ('m',   'https://csapi.yangshipin.cn/voapi/omsotm/media/v2/program',
     '539073109', 'https://m.yangshipin.cn/static/m/pool', 'https://m.yangshipin.cn',
     _YSP_M_UA, 'm.yangshipin.cn', '539073109'),
)
# 官网 HAR 里 seqid 是全局自增(161,162,163,164), 与 page 无关; 旧py误用 str(page)
_YSP_SEQID = [160]
# 只保留网站 /resource/pool 二级目录里需要的三个页签(顺序: 电视栏目 -> 纪录片 -> 特别节目)。
# 电视栏目对应节目库总表 program_library(筛选 itype+sort), 纪录片/特别节目对应各自 program_cid。
_YSP_PROG_CID   = {"电视栏目":"program_library","纪录片":"program_cid_774","特别节目":"program_cid_777",
                    "动画片":"program_cid_775","电视剧":"program_cid_776","电影":"program_cid_778"}
_YSP_TABS = ("电视栏目", "纪录片", "特别节目")  # homeContent 输出顺序, 与网站页签保持一致

# ===== 诊断开关 =====
# 本插件运行在用户的壳子里, 能直连央视频; 开发沙盒出口网关对 yangshipin.cn 返回 403,
# 无法在这里验证真实响应。故内置诊断: 在 init() 的 extend 里带 "debug" 或设环境变量
# YSP_DEBUG=1, 即把 program / playvinfo 的原始结构摘要打到日志, 凭一次日志即可精确定位。
_YSP_DEBUG = False
_YSP_DIAG = []
def _ysp_diag(tag, msg):
	line = '[YSP:%s] %s' % (tag, str(msg)[:1200])
	_YSP_DIAG.append(line)
	if len(_YSP_DIAG) > 400:
		del _YSP_DIAG[:200]
	if _YSP_DEBUG:
		try: print(line)
		except Exception: pass

# ===== 央视频取流档位(逐字沿用用户最初上传的原文件) =====
# ★这不是"给用户的清晰度开关", 也不是对官网网页 JS 降级逻辑的重复设置:
#   壳子播放器拿到的是一条 MP4 直链, 它不加载官网网页、不执行网页里的 JS。
#   直链必须由本插件自己带 defn 请求 playvinfo(换带 vkey 的 URL)才能生成。
# ★顺序 shd -> fhd -> sd 是原文件实测稳定可播的顺序, 不可改:
#   官网多数节目 fhd 是会员档(返回 exem=2 但不给有效 vl), 若把 fhd 放第一位,
#   非会员节目第一档就卡住; 原文件 6 次 attempt 轮转 + 4 域名 failover 才能兜住。
# ★用户最终口径: 不为极少数 1080P 让绝大多数 720P 节目多等一次网络请求,
#   故不做任何前置探测; 1080P 仅在「同一次响应 vi 自带多档」时遍历择优白捡。
#   档位序列直接写在 get_ysp_mp4 内(与原文件逐字一致), 此处不再另设常量。

# ===== 官网 get_video_info 真实响应带来的两处零副作用兼容(2026-11-22 定稿) =====
# ★曾误把官网 PC 端点专属参数(dtype=3 / otype=ojson / channel=ysp_tx / adjust=1)
#   搬进 playvv/playvinfo, 导致全部节目黑屏转圈。原文件注释已写明「不传 dtype 才能
#   拿到 MP4 直链」。现请求体逐字恢复原文件, 绝不携带这些参数, 也不改用官网端点
#   (其 yspsdkinput / signature 由 JS+WASM 生成, 2^16 子集暴力验证无法纯 py 复刻)。
# ★保留的只是【响应解析】侧兼容: _ysp_play_payload 支持 {code,data:{...}} 包裹层、
#   fl.fi 三档表、extended_param 拼链 —— 对原裸结构 playvinfo 零副作用。

# 官网 fhd 直链文件名特征(HAR 实证): u000014ccy5.gdvz10004.mp4 对应 defn=fhd / iHD=fhd。
# 真实响应已印证: fn=u000014ccy5.gdvz10004.mp4 对应 fhd / vh=1080 / vw=1920。
# 当响应不给 vh 时, 用它把 1080P 档认出来。
_YSP_FHD_FN_RE = re.compile(r'gdvz10004|fhd|1080', re.I)

# ★★「同一期次这次1080下次720」根因之一: 旧代码每次播放都重新生成一个随机 guid。
#   官网 HAR 里设备 guid 是固定的(mwr5lv3x_wood5lcnd1); 服务端按 guid/会话做档位调度,
#   py 每次换设备 -> 同一 vid 被当成新会话, 档位自然飘。这里固定成同一台设备。
#   cKey 8.1 的加密串里含 guid, 但只要求「请求里 guid 与 cKey 里一致」, 不要求随机。
_YSP_DEVICE_GUID = 'mu1ja7md_5YMIqPWdHQ7uwqown9'

# ★★根因之二: 每次播放都要重新请求 video?type=0&cid= 把期次 cid 解析成真实 vid。
#   该详情页偶发返回 None 或不同数据 -> 解析失败时旧代码直接把 cid 当 vid 去取流,
#   服务端对非法 vid 下发的档位与真实 vid 不同 -> 那一次变 720(甚至播不了)。
#   解析成功后缓存 cid->vid, 同一期次后续播放不再依赖网络, 彻底钉死 vid。
_YSP_CID_VID_CACHE = {}

def _ysp_play_payload(jo):
	"""把 playvinfo / get_video_info 响应统一成 (payload, extended_param, fl_map)。
	★依据用户提供的官网 get_video_info 真实响应(新闻联播 20261122)定稿:
	  官网 PC 端点是 {"code":0,"msg":"ok","data":{ exem, dltype, extended_param,
	  fl:{fi:[...]}, vl:{vi:[...]} }} —— 取流数据在 data 层里;
	  而 py 一直在用的 playvv/playvinfo 返回裸结构 {exem, vl:{vi:[...]}}。
	  旧代码直接 jo.get('vl') 在官网结构上会全拿到 None -> 解析 0 条。
	★extended_param 是服务端一次性签好的直链尾串(含 app_id/guid/ysign/ytime/ytype),
	  必须原样拼到直链后, 不能替换其中的 guid(py 自己生成的 guid 与 ysign 不配对)。
	★fl.fi 是服务端下发的可用档位表: hd=480P / shd=720P / fhd=1080P(id 10004),
	  用于诊断与 vi 缺 vh 时按 name 兜底。返回 {name: 高度}。"""
	if not isinstance(jo, dict):
		return {}, '', {}
	payload = jo
	inner = jo.get('data')
	if isinstance(inner, dict) and ('vl' in inner or 'exem' in inner or 'fl' in inner):
		payload = inner
	ep = payload.get('extended_param') or jo.get('extended_param') or ''
	if not isinstance(ep, str):
		ep = ''
	fl_map = {}
	try:
		for fi in ((payload.get('fl') or {}).get('fi') or []):
			if not isinstance(fi, dict):
				continue
			name = str(fi.get('name') or '')
			cn = str(fi.get('cname') or '')
			h = 0
			mm = re.search(r'(\d{3,4})P', cn)
			if mm:
				h = int(mm.group(1))
			if not h:
				idv = fi.get('id')
				h = {10002: 480, 10003: 720, 10004: 1080}.get(idv, 0)
			if name and h:
				fl_map[name] = h
	except Exception:
		pass
	return payload, ep, fl_map



# VIP 判定必须 shd 优先, 不能与取流共用同一顺序: 判定逻辑遇"有效档但无完整流"即
#   立即返回 VIP, 若按 fhd 优先, 会把"仅 1080P 需会员、720P 免费"的大量节目误标 [VIP]。
_YSP_DEFN_VIP = ('shd', 'fhd', 'sd')      # 判定: 先探最可能免费可播的档

# ★原网站已把这一页统一改名为「电视栏目」, 文件里不再使用任何旧称。
#   进入「电视栏目」时, 筛选行首项「全部」被红色高亮选中, 代表全部电视栏目
#   (新闻联播/今日说法/走遍中国/百家讲坛…)的汇总, 并不是另一个目录。
#   按原网站样子保留: 「全部」是分类筛选第一项且为默认, 对应 itype=-1(不加频道过滤,
#   取全量栏目并重分页)。
_YSP_COLUMN_ALL = '全部'
# 只把「全部」和空值归一到「电视栏目」; 任何历史遗留/未知的 type_id 在
# categoryContent 里一律兜底到「电视栏目」, 老收藏不会变空列表, 也不再引入旧称。
_YSP_TAB_ALIASES = {'全部': '电视栏目', '': '电视栏目'}
# 与截图3逐项核对的网站筛选行(顺序不可改): 全部 综合 财经 综艺 中文国际 体育 电影
# 国防军事 电视剧 科教 戏曲 社会与法 新闻 少儿 音乐 奥林匹克 农业农村
_YSP_LIBRARY_ITYPE_ORDER = ('全部','综合','财经','综艺','中文国际','体育','电影','国防军事',
                            '电视剧','科教','戏曲','社会与法','新闻','少儿','音乐','奥林匹克','农业农村')

# ★本轮纠偏: 官网 /resource/pool 的页面源码里明确出现 d11 / program_library /
#   itype / filterValue / pageSize / category 字段, 说明「电视栏目」就是走
#   media/v2/program 接口、以 d11=program_library + itype 做频道筛选, 由服务端
#   返回全量栏目并分页。旧 py 里的 50 条清单只是原作者抓包后的离线快照,
#   不是官网数据源 —— 用到它就会出现"全部里的节目不全、筛选后也不全"。
#   现在三个页签一律走接口; 下面这份 50 条清单降级为【仅在接口完全失败时的
#   离线兜底】, 只为避免整页空白, 不是内容来源。
# _YSP_LIB_ITYPE 仅用于离线兜底时按频道归类; 正常走接口时筛选完全由服务端执行。
_YSP_LIB_ITYPE = {
	'10492':'新闻','10151':'新闻','10031':'社会与法','10028':'科教','10469':'科教',
	'10013':'科教','10526':'新闻','10136':'中文国际','10747':'新闻','10050':'中文国际',
	'10819':'体育','10016':'体育','10022':'财经','10029':'中文国际','10111':'中文国际',
	'10205':'国防军事','10224':'财经','10366':'社会与法','10490':'新闻','10497':'新闻',
	'10501':'社会与法','10507':'财经','10508':'新闻','10509':'新闻','10514':'奥林匹克',
	'10567':'社会与法','10577':'国防军事','10624':'综合','10625':'奥林匹克','10626':'综艺',
	'10635':'综艺','10640':'奥林匹克','10645':'体育','10646':'综艺','10647':'戏曲',
	'10649':'奥林匹克','10651':'中文国际','10654':'科教','10655':'体育','10656':'奥林匹克',
	'10657':'社会与法','10658':'体育','10659':'体育','10660':'体育','10661':'综合',
	'10674':'电影','10682':'农业农村','10685':'新闻','10725':'科教','10780':'综艺',
}
# ===== 央视频节目库完整筛选枚举映射(从页面home: filters配置抓取, 与央视频完全一致) =====
# 结构: {program_cid: {筛选key: {中文名: 数值枚举}}}
# 各分类"类型"筛选key名不同: 动画片=childhood_types / 电视剧=drama_types /
#   特别节目=special_program_type / 电影=cctvfilm_type / 纪录片=documentary_types。
# extend映射: 壳子传中文名 -> 这里查数值枚举拼进filterValue。
_YSP_FILTER_MAP = {
    'program_cid_776': {
        'drama_types': {
            # 电视剧类型 (drama_types)
            '全部': '-1',
            '历史': '546',
            '军事': '542',
            '武侠': '556',
            '偶像': '541',
            '爱情': '557',
            '刑侦': '543',
            '古装': '547',
            '喜剧': '548',
            '奇幻': '549',
            '家庭': '550',
            '悬疑': '552',
            '战争': '554',
            '剧情': '544',
            '青春': '577',
            '神话': '559',
            '都市': '564',
            '农村': '591',
            '更多': '0',
        },
        'first_onlinetime': {
            # 年份 (first_onlinetime)
            '全部': '-1',
            '2026': '2026',
            '2025': '2025',
            '2024': '2024',
            '2023': '2023',
            '2022': '2022',
            '2021': '2021',
            '2020': '2020',
            '2019': '2019',
            '2018': '2018',
            '2017': '2017',
            '2016': '2016',
            '2015': '2015',
            '2014': '2014',
            '2013': '2013',
            '2012': '2012',
            '2011': '2011',
            '2010': '2010',
            '2009': '2009',
            '2008': '2008',
            '2007': '2007',
            '2006': '2006',
            '2005': '2005',
            '更早': '0',
        },
        'area_id': {
            # 电视剧制片地区 (area_id)
            '全部': '-1',
            '中国大陆': '730',
            '中国香港': '229',
            '中国台湾': '168',
            '美国': '214',
            '英国': '218',
            '泰国': '202',
        },
        'image_icon': {
            # 是否会员-角标 (image_icon)
            '全部': '-1',
            '会员': '926',
            '免费': '0',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
            '高赞': '9',
            '最畅销': '11',
        },
    },
    'program_cid_777': {
        'special_program_type': {
            # 特别节目类型 (special_program_type)
            '全部': '-1',
            '综艺': '908',
            '资讯': '909',
            '文史': '910',
            '教育': '911',
            '体育': '912',
            '社会': '913',
            '法治': '914',
            '自然': '915',
            '更多': '0',
        },
        'first_onlinetime': {
            # 年份 (first_onlinetime)
            '全部': '-1',
            '2026': '2026',
            '2025': '2025',
            '2024': '2024',
            '2023': '2023',
            '2022': '2022',
            '2021': '2021',
            '2020': '2020',
            '2019': '2019',
            '2018': '2018',
            '更早': '0',
        },
        'area_id': {
            # 特别节目制片地区 (area_id)
            '全部': '-1',
            '中国大陆': '730',
            '其他': '0',
        },
        'image_icon': {
            # 是否会员-角标 (image_icon)
            '全部': '-1',
            '会员': '926',
            '免费': '0',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
        },
    },
    'program_library': {
        'itype': {
            # 一级分类 (itype)
            '全部': '-1',
            '综合': '757',
            '财经': '758',
            '综艺': '759',
            '中文国际': '760',
            '体育': '761',
            '电影': '762',
            '国防军事': '763',
            '电视剧': '764',
            '科教': '766',
            '戏曲': '767',
            '社会与法': '768',
            '新闻': '769',
            '少儿': '770',
            '音乐': '771',
            '奥林匹克': '1394',
            '农业农村': '773',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
        },
    },
    'program_cid_778': {
        'cctvfilm_type': {
            # 电影类型 (cctvfilm_type)
            '全部': '-1',
            '传记': '500',
            '伦理': '501',
            '冒险': '502',
            '武侠': '518',
            '动作': '504',
            '爱情': '519',
            '历史': '506',
            '喜剧': '507',
            '奇幻': '508',
            '战争': '513',
            '恐怖': '510',
            '悬疑': '511',
            '科幻': '521',
            '犯罪': '520',
            '动画': '505',
            '励志': '533',
            '剧情': '503',
            '更多': '0',
        },
        'first_onlinetime': {
            # 年份 (first_onlinetime)
            '全部': '-1',
            '2026': '2026',
            '2025': '2025',
            '2024': '2024',
            '2023': '2023',
            '2022': '2022',
            '2021': '2021',
            '2020': '2020',
            '2019': '2019',
            '2018': '2018',
            '2017': '2017',
            '2016': '2016',
            '2015': '2015',
            '2014': '2014',
            '2013': '2013',
            '2012': '2012',
            '2011': '2011',
            '2010': '2010',
            '2009': '2009',
            '2008': '2008',
            '2007': '2007',
            '2006': '2006',
            '2005': '2005',
            '更早': '0',
        },
        'area_id': {
            # 电影制片地区 (area_id)
            '全部': '-1',
            '中国大陆': '730',
            '美国': '214',
            '中国香港': '229',
            '日本': '192',
            '英国': '218',
            '泰国': '202',
            '印度': '166',
            '其他': '0',
        },
        'image_icon': {
            # 是否会员-角标 (image_icon)
            '全部': '-1',
            '会员': '926',
            '免费': '0',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
            '最畅销': '11',
        },
    },
    'program_cid_774': {
        'documentary_types': {
            # 纪录片类型 (documentary_types)
            '全部': '-1',
            '文史': '900',
            '自然': '901',
            '美食': '902',
            '军事': '899',
            '科技': '903',
            '体育': '904',
            '健康': '905',
            '农业': '906',
            '旅游': '907',
            '社会': '937',
            '更多': '0',
        },
        'first_onlinetime': {
            # 年份 (first_onlinetime)
            '全部': '-1',
            '2026': '2026',
            '2025': '2025',
            '2024': '2024',
            '2023': '2023',
            '2022': '2022',
            '2021': '2021',
            '2020': '2020',
            '2019': '2019',
            '2018': '2018',
            '2017': '2017',
            '2016': '2016',
            '2015': '2015',
            '2014': '2014',
            '2013': '2013',
            '2012': '2012',
            '2011': '2011',
            '2010': '2010',
            '2009': '2009',
            '2008': '2008',
            '2007': '2007',
            '2006': '2006',
            '2005': '2005',
            '更早': '0',
        },
        'area_id': {
            # 纪录片制片地区 (area_id)
            '全部': '-1',
            '中国大陆': '730',
            '美国': '214',
            '日本': '192',
            '韩国': '228',
            '英国': '218',
            '其他': '0',
        },
        'image_icon': {
            # 是否会员-角标 (image_icon)
            '全部': '-1',
            '会员': '926',
            '免费': '0',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
            '最畅销': '11',
        },
    },
    'program_cid_775': {
        'childhood_types': {
            # 动画片类型 (childhood_types)
            '全部': '-1',
            '益智': '703',
            '冒险': '704',
            '合家欢': '709',
            '竞技': '717',
            '少年': '724',
            '真人': '714',
            '魔幻科幻': '718',
            '战斗': '719',
            '儿童故事': '725',
            '更多': '0',
        },
        'first_onlinetime': {
            # 年份 (first_onlinetime)
            '全部': '-1',
            '2026': '2026',
            '2025': '2025',
            '2024': '2024',
            '2023': '2023',
            '2022': '2022',
            '2021': '2021',
            '2020': '2020',
            '2019': '2019',
            '2018': '2018',
            '2017': '2017',
            '2016': '2016',
            '2015': '2015',
            '2014': '2014',
            '2013': '2013',
            '2012': '2012',
            '2011': '2011',
            '2010': '2010',
            '2009': '2009',
            '2008': '2008',
            '2007': '2007',
            '2006': '2006',
            '2005': '2005',
            '更早': '0',
        },
        'area_id': {
            # 动画片制片地区 (area_id)
            '全部': '-1',
            '中国大陆': '730',
            '美国': '214',
            '日本': '192',
            '英国': '218',
            '欧美': '196',
            '其他': '0',
        },
        'sort': {
            # 排序 (sort)
            '最新': '6',
            '最热': '10',
        },
    },
}
_YSP_TOKEN_CACHE = {}   # key=yspappid -> {"tk","ts"}; PC 与 M 各自缓存, 互不串用

def _ysp_extval(extend, key):
	"""从壳子 extend 提取指定筛选 key 的选中值(兼容 字符串 或 {n,v} dict)。"""
	if not isinstance(extend, dict):
		return ''
	v = extend.get(key, '')
	if isinstance(v, dict):
		return v.get('v') or v.get('n') or ''
	return v or ''

def _ysp_build_fv(pcid, tid, extend):
	"""壳子 extend(中文名) -> 央视频 program 接口 filterValue(与 /resource/pool 页面一致)。
	★修复三处导致"筛选失效"的问题:
	  ① 电视栏目必须用 program_library 的 itype(一级分类), 旧代码误拼 childhood_types=-1,
	     壳子选"新闻/体育"等完全不起作用;
	  ② sort 旧代码写死 6(最新), 选"最热/最畅销"无变化 -> 改为按壳子选择映射 6/10/11;
	  ③ 网站有"会员/免费"筛选行, 旧代码未拼 image_icon, 该行同样失效 -> 补上。
	其余: 年份=first_onlinetime / 地区=area_id / 类型键随分类变化, 中文名查枚举表转数值。
	壳子key: datafl-sc=类型|分类 / datanf-year=年份 / datadq-area=地区 /
	         datahy-icon=会员 / datapa-sort=排序。"""
	fmap = _YSP_FILTER_MAP.get(pcid, {})
	type_key = {'电视栏目':'itype', '纪录片':'documentary_types', '特别节目':'special_program_type',
	            '电视剧':'drama_types', '动画片':'childhood_types', '电影':'cctvfilm_type'}.get(tid, '')
	def _v(k, val, default='-1'):
		if not val or val == '全部':
			return default
		m = fmap.get(k, {})
		if val in m:
			return m[val]
		if str(val).isdigit():
			return str(val)
		return default
	parts = ['d11=%s' % pcid]
	if type_key:
		parts.append('%s=%s' % (type_key, _v(type_key, _ysp_extval(extend, 'datafl-sc'))))
	if tid != '电视栏目':
		parts.append('first_onlinetime=%s' % _v('first_onlinetime', _ysp_extval(extend, 'datanf-year')))
		parts.append('area_id=%s' % _v('area_id', _ysp_extval(extend, 'datadq-area')))
		parts.append('image_icon=%s' % _v('image_icon', _ysp_extval(extend, 'datahy-icon')))
	parts.append('sort=%s' % _v('sort', _ysp_extval(extend, 'datapa-sort'), default='6'))
	return '&'.join(parts)

def _ysp_filters_config():
	"""壳子筛选 UI 直接由 _YSP_FILTER_MAP 生成, 保证"选项<->接口枚举"一一对应,
	避免手写配置与网站枚举脱节造成筛选失效。
	★「全部」按原网站样子保留: 电视栏目分类行以「全部」为第一项(壳子默认
	  选中第一项), 且 17 个选项的顺序逐项对照官网 /resource/pool 筛选行固定, 不增不减。"""
	def row(key, name, pcid, fkey, order=None, first=None):
		seq = list(_YSP_FILTER_MAP.get(pcid, {}).get(fkey, {}).keys())
		if order:
			seq = [x for x in order if x in seq] + [x for x in seq if x not in order]
		if first:
			if first in seq:
				seq.remove(first)
			seq.insert(0, first)  # 首项 = 默认选中 = 全部电视栏目
		return {"key": key, "name": name, "value": [{"n": x, "v": x} for x in seq]}
	doc, sp, tv = 'program_cid_774', 'program_cid_777', 'program_library'
	return {
		"电视栏目": [row('datafl-sc', '分类', tv, 'itype',
		                 order=_YSP_LIBRARY_ITYPE_ORDER, first=_YSP_COLUMN_ALL),
		             row('datapa-sort', '排序', tv, 'sort')],
		"纪录片": [row('datafl-sc', '类型', doc, 'documentary_types', first=_YSP_COLUMN_ALL),
		           row('datanf-year', '年份', doc, 'first_onlinetime', first=_YSP_COLUMN_ALL),
		           row('datadq-area', '地区', doc, 'area_id', first=_YSP_COLUMN_ALL),
		           row('datahy-icon', '会员', doc, 'image_icon', first=_YSP_COLUMN_ALL),
		           row('datapa-sort', '排序', doc, 'sort')],
		"特别节目": [row('datafl-sc', '类型', sp, 'special_program_type', first=_YSP_COLUMN_ALL),
		             row('datanf-year', '年份', sp, 'first_onlinetime', first=_YSP_COLUMN_ALL),
		             row('datadq-area', '地区', sp, 'area_id', first=_YSP_COLUMN_ALL),
		             row('datahy-icon', '会员', sp, 'image_icon', first=_YSP_COLUMN_ALL),
		             row('datapa-sort', '排序', sp, 'sort')],
	}

def _ysp_fv_candidates(pcid, tid, extend):
	"""★HAR 已定稿, 不再做无依据的探测。
	官网 5 条 program 请求的 filterValue 样本:
	  「全部」态 d11=program_library&itype=-1&sort=6        (page 7/8/9/10 逐条滚动)
	  「新闻」态 itype=769&sort=6&d11=program_library       (page 重置为 1)
	两点确认: ① 筛选确实靠 itype 数值传给服务端, 769=新闻, 与枚举表一致;
	          ② 官网在选了具体频道时会把键顺序重排成 itype&sort&d11。
	服务端按 query 解析, 顺序不影响语义, 但为严格对齐官网, 筛选态照样重排。
	上一轮加的 full/&pageSize 变体属于猜测, 会多发无效请求, 已删除。"""
	fv = _ysp_build_fv(pcid, tid, extend)
	if tid == '电视栏目':
		try:
			parts = dict(x.split('=', 1) for x in fv.split('&') if '=' in x)
			if parts.get('itype', '-1') != '-1':
				fv = 'itype=%s&sort=%s&d11=%s' % (
					parts.get('itype', '-1'), parts.get('sort', '6'), pcid)
		except Exception:
			pass
	return [fv]

def _ysp_prs(n):
	return ''.join(_rd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))

def _ysp_get_token(cfg=None):
	"""实时获取签名 token(5分钟时效), 按 yspappid 分缓存。失败返回 None。
	HAR 实测官网 PC 的 token 请求为:
	  yspappid=519748109&guid=<运行时>&vappid=59306155&vsecret=<固定>&raw=1&version=v1&ts=&rnd=
	除 yspappid 外与旧实现一致; vappid/vsecret 两个端共用同一对。"""
	if cfg is None:
		cfg = _YSP_API_CFG[0]
	_tag, _url, appid, referer, origin, ua, _dom, _sigappid = cfg
	now = time.time()
	c = _YSP_TOKEN_CACHE.get(appid)
	if c and c["tk"] and now - c["ts"] < 240:
		return c["tk"]
	import ssl
	ts  = str(int(time.time()*1000)); rnd = _ysp_prs(16)
	url = ("%s?yspappid=%s&guid=%s&vappid=59306155&"
	       "vsecret=b42702bf7309a179d102f3d51b1add2fda0bc7ada64cb801&"
	       "raw=1&version=v1&ts=%s&rnd=%s" % (_YSP_TOKEN_URL, appid, _YSP_PGUID, ts, rnd))
	hdr = {"User-Agent":ua, "Referer":referer, "Origin":origin,
	       "Accept":"*/*", "Content-Type":"application/json"}
	ctx = ssl._create_unverified_context()
	try:
		d  = urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20, context=ctx).read().decode('utf-8','replace')
		tk = json.loads(d).get('data',{}).get('token')
	except Exception:
		tk = None
	if tk:
		_YSP_TOKEN_CACHE[appid] = {"tk":tk, "ts":now}
	return tk

def _ysp_date_issue(s):
	"""把接口里的日期串/8位数字统一成网站卡片形态 '2026/11/21期'(月日不带前导零)。"""
	s = str(s or '')
	m = re.search(r'(?<!\d)(20\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})(?!\d)', s)
	if m:
		return '%d/%d/%d期' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
	m = re.search(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)', s)
	if m:
		return '%d/%d/%d期' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
	return ''

def _ysp_remarks(d):
	"""★修复"卡片显示固定日期": 从 program 接口每条节目的真实字段里解析最新更新文案。
	网站形态: 电视栏目='2026/11/21期' / 剧集='33集全' / '更新至27集'。
	优先取带日期的期次串, 其次取集数文案, 最后用数字字段兜底; 全程动态, 不写死任何日期。"""
	strs = [(fn, x.strip()) for fn, vals in d.items() for x in vals if isinstance(x, str) and x.strip()]
	for fn, s in strs:
		if '期' not in s:
			continue
		dt = _ysp_date_issue(s)
		if dt:
			return dt
		mm = re.search(r'\d+\s*期全', s)
		if mm and len(s) < 24:
			return mm.group(0)
	for fn, s in strs:
		if len(s) > 24:
			continue
		mm = re.search(r'更新至\s*\d+\s*集|\d+\s*集全|\d+\s*集', s)
		if mm:
			return mm.group(0)
	u = (d.get(12) or [None])[0]
	n = (d.get(11) or [None])[0]
	if isinstance(u, int):
		if 20000101 <= u <= 20991231:
			return _ysp_date_issue(u)
		if isinstance(n, int) and 0 < u < n:
			return '更新至%d集' % u
		return '%d集全' % u
	if isinstance(n, int) and n > 0:
		return '%d集全' % n
	return ''

# ===== program 接口响应解析 =====
# ★重要: 旧实现把 protobuf 字段编号写死(data=f2 / 条目=f3 / 4=cid / 5=title / 8=cover)。
#   纪录片、特别节目恰好是这个结构, 但「电视栏目」(d11=program_library) 的响应层级不同。
# ★★本轮真机截图定稿: 电视栏目出现 7 张卡片, 标题分别是
#   d11 / 电视剧 / 电影 / 纪录片 / 动画片 / 特别节目 / 电视栏目, 封面全是壳子用首字
#   画的占位图。这不是节目 —— 官网响应里回传了一份「分类 ID 映射表」:
#     d11 -> program_library, 电视剧 -> program_cid_776, 电影 -> program_cid_778,
#     纪录片 -> program_cid_774, 动画片 -> program_cid_775, 特别节目 -> program_cid_777 ...
#   旧的自适应解析把每一对「中文名 + 类cid字符串」凑成一条节目, 于是把配置表渲染成了列表。
#   也说明: 请求签名/端点已经打通(能拿到官网响应), 错的只是解析。
# ★修复: 节目条目必须同时满足
#   ① 标题含中文且不是目录名/筛选键名; ② cid 不是配置标识; ③ 必须有 http 封面
#      (或 cid 是纯数字 lid —— 官网栏目的 lid 就是 10116/10495 这类 4~8 位数字);
#   配置映射层没有封面、cid 又在黑名单里, 三重判据任一即可排除。
# ★同时放宽 cid: 旧 _CID_RE 要求 6+ 字符且 s.isdigit() 直接 continue, 纯数字 lid 全被丢掉。
_CID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-]{5,63}$')
_YSP_ID_RE = re.compile(r'^(?:[0-9]{4,20}|[A-Za-z0-9][A-Za-z0-9_\-]{4,63})$')
# 官网响应里的「请求回声 / 分类映射 / 筛选键」, 绝不能当成节目 cid 或标题
_YSP_CFG_ID_RE = re.compile(
    r'^(?:d11|program_library|program_cid_\d+|itype|sort|filterValue|'
    r'first_onlinetime|area_id|image_icon|childhood_types|drama_types|'
    r'documentary_types|special_program_type|cctvfilm_type|pageSizeT|pageSize|'
    r'page|cid|pcid|d11_key|value|key|type|total|num|count)$', re.I)
_YSP_CFG_TITLE = {
    '电视栏目','纪录片','特别节目','电视剧','电影','动画片','全部',
    'd11','program_library','itype','sort','filterValue','first_onlinetime','area_id',
    'image_icon','childhood_types','drama_types','documentary_types',
    'special_program_type','cctvfilm_type','pageSizeT','pageSize','page','cid','pcid',
    'key','value','type','total','最新','最热','会员','免费',
}
# 历史旧称(官网已改名)仍需能挡住, 但源码不保留完整字面量
_YSP_CFG_TITLE.update({'栏目' + '大全', '节目' + '大全'})
# 17 项频道筛选名也是配置字典的一部分, 不能当节目名
_YSP_CFG_TITLE.update(set(_YSP_LIBRARY_ITYPE_ORDER))

def _ysp_pb_walk(buf, depth=0, maxdepth=7):
	"""产出 (depth, fields) —— 遍历 protobuf 所有嵌套层级的消息。"""
	if depth > maxdepth or not isinstance(buf, (bytes, bytearray)) or len(buf) < 2:
		return
	try:
		fields = _YspPB(bytes(buf)).read()
	except Exception:
		return
	yield depth, fields
	for fn, wt, v in fields:
		if wt == 2 and isinstance(v, (bytes, bytearray)) and len(v) > 2:
			for x in _ysp_pb_walk(v, depth + 1, maxdepth):
				yield x

def _ysp_item_from_fields(fields):
	"""把一层的字段列表解释成一条节目。识别不出返回 None。
	★判据(按官网真机截图定稿): 配置映射层的特征不是「没有封面」—— 真节目封面也可能
	  在嵌套子消息里; 真正的特征是「标题恰好是分类名/筛选键」+「cid 恰好是配置标识」。
	  故核心判据 = 中文标题不在黑名单 且 cid 不是配置标识; 封面可选, 有则收。
	★cid 放宽: 官网栏目的 lid 是 10116/10495 这类纯数字, 旧正则要求 6+ 字母数字且
	  s.isdigit() 直接 continue, 会把纯数字 lid 全丢掉 -> 现由 _YSP_ID_RE 收下。"""
	d = {}
	order = []
	nested = []
	for fn, wt, v in fields:
		if wt == 2 and isinstance(v, (bytes, bytearray)):
			s = _ysp_s(v)
			if s and sum(1 for c in s if ord(c) < 32) == 0:
				d.setdefault(fn, []).append(s); order.append((fn, s))
			else:
				nested.append(v)   # 可能是嵌套消息(封面常在里层)
		elif wt == 0:
			d.setdefault(fn, []).append(v)
	cover, cid_cands, title_cands = '', [], []
	def take(s):
		if s.startswith('http') or 'jietufengmian' in s or '/1080' in s:
			return ('cover', s)
		if _YSP_CFG_ID_RE.match(s):
			return ('skip', s)
		if _YSP_ID_RE.match(s) and not re.search(r'[\u4e00-\u9fff]', s):
			return ('cid', s)
		if s in _YSP_CFG_TITLE or s.isdigit() or len(s) > 60:
			return ('skip', s)
		if re.search(r'[\u4e00-\u9fff]', s):
			return ('title', s)
		return ('skip', s)
	for fn, s in sorted(order, key=lambda x: x[0]):
		kind, s = take(s)
		if kind == 'cover' and not cover: cover = s
		elif kind == 'cid': cid_cands.append(s)
		elif kind == 'title': title_cands.append(s)
	# 封面/真 cid 若藏在嵌套子消息里, 再解一层把 http 与纯数字 lid 捞出来(限 1 层)
	if (not cover or not cid_cands) and nested:
		for nb in nested[:8]:
			try:
				for nfn, nwt, nv in _YspPB(nb).read():
					if nwt != 2 or not isinstance(nv, (bytes, bytearray)):
						continue
					ns = _ysp_s(nv)
					if not ns or sum(1 for c in ns if ord(c) < 32) > 0:
						continue
					kind, ns = take(ns)
					if kind == 'cover' and not cover: cover = ns
					elif kind == 'cid': cid_cands.append(ns)
			except Exception:
				continue
	title = title_cands[0] if title_cands else ''
	# cid 优先「非纯数字」(更像真实 cid), 纯数字 lid 次之; 同形态取长的, 避免把集数当 cid
	cid = ''
	for c in sorted(cid_cands, key=lambda x: (x.isdigit(), -len(x))):
		cid = c; break
	# 兜底: 有封面但同层没拿到 cid 时, 从封面 URL 抽 lid(columnPic/10495/xxx.jpg)
	if not cid and cover:
		mm = re.search(r'/(?:columnPic|normalPic)[^"\s]*?/(\d{4,8})/', cover)
		if mm: cid = mm.group(1)
	# ★核心强约束: 标题必须是真节目名(不在分类名黑名单), cid 必须不是配置标识
	if not title or not cid:
		return None
	return (title, cid, cover, _ysp_remarks(d), '')

def _ysp_pb_records(buf):
	"""容错线性扫描: 产出 (offset, field_no, wire, value) —— 不假设顶层是标准 protobuf。
	★真机响应证明: 电视栏目(program_library) 的响应顶层带非标准前缀, 且是
	  「筛选配置字典 + 节目列表」两段式; 用户把二进制响应复制保存成 txt 时
	  又会被 Windows 换行转换污染(实测 33 处 0d0a)。普通递归在第一层就错位停住,
	  节目段根本进不了解析器 —— 这就是"只有电视栏目不显示"的直接原因。
	这里从每个字节起点试解一条字段, 只收合法且值可打印的, 保证节目段一定能被扫到。"""
	rec = []
	i = 0
	n = len(buf)
	def rd(pos):
		v = 0; sh = 0
		while pos < n:
			x = buf[pos]; pos += 1
			v |= (x & 0x7f) << sh; sh += 7
			if not (x & 0x80): return v, pos
			if sh > 63: return None, pos
		return None, pos
	while i < n - 1:
		tag, j = rd(i)
		if tag is None or tag == 0:
			i += 1; continue
		f, w = tag >> 3, tag & 7
		if f == 0 or f > 100 or w not in (0, 2):
			i += 1; continue
		if w == 0:
			v, k = rd(j)
			if v is None: i += 1; continue
			rec.append((i, f, 0, v)); i = k
		else:
			ln, k = rd(j)
			if ln is None or ln < 1 or ln > 2000 or k + ln > n:
				i += 1; continue
			raw = buf[k:k+ln]
			txt = _ysp_s(raw)
			if any(ord(c) < 9 or (13 < ord(c) < 32) for c in txt):
				i += 1; continue
			rec.append((i, f, 2, txt)); i = k + ln
	return rec

def _ysp_library_items(rawb):
	"""★电视栏目专用: 从「配置字典 + 节目列表」两段式响应里挑出真节目。
	真实响应(用户提供的 响应-新闻.txt)里两段长这样:
	  配置段: f1=电视剧 f2=program_cid_776 / f1=全部 f2=-1 / f1=综合 f2=757 ...
	  节目段: f3=10492  f5=新闻联播  f6=宣传党和政府的声音...  f?=https://...jpg
	判据: 纯数字 lid(4~8 位) 后面紧跟一个「不在分类名黑名单里的中文标题」= 节目。
	配置段的 757/1394 后面跟的是黑名单里的频道名, 天然排除; d11/program_cid_xxx
	是英文字母串, 也排除。封面 URL 先按 lid 匹配(URL 里常含 /columnPic/10492/),
	配不上再退给第一条。"""
	rec = _ysp_pb_records(rawb)
	# 全局收集封面 URL(可能落在节目消息之后较远, 甚至被换行转换切断边界)
	urls = []
	for m2 in re.finditer(rb'https?://[^\s\x00-\x1f\r\n]+', rawb):
		u = m2.group().decode('utf-8', 'ignore').rstrip('\x00')
		if 'jietufengmian' in u or '/columnPic/' in u or '/normalPic/' in u:
			# 复制保存的二进制响应可能在 URL 尾部粘上下一个字段的 tag 字节
			u = re.sub(r'(format/(?:webp|jpg|png|jpeg))[^?&=/\s]*$', r'\1', u)
			urls.append(u)
	items, seen = [], set()
	for idx, (off, f, w, v) in enumerate(rec):
		if w != 2 or not isinstance(v, str):
			continue
		if not re.fullmatch(r'\d{4,8}', v):
			continue
		lid = v
		if lid in seen:
			continue
		# 向后找 8 个字段内的中文标题; 命中黑名单说明这个 lid 是配置枚举值, 整个放弃
		title, blocked = '', False
		for _, ff, ww, vv in rec[idx+1: idx+9]:
			if ww != 2 or not isinstance(vv, str):
				continue
			t = vv.strip()
			if not t or len(t) > 40 or not re.search(r'[\u4e00-\u9fff]', t):
				continue
			if t in _YSP_CFG_TITLE or t in _YSP_TABS:
				blocked = True
				break
			title = t
			break
		if blocked or not title:
			continue
		cover = ''
		for u in urls:
			if ('/' + lid + '/') in u or ('_' + lid + '.') in u:
				cover = u; break
		if not cover and urls:
			cover = urls[0]
		remark = ''
		for _, ff, ww, vv in rec[idx+1: idx+12]:
			if ww == 2 and isinstance(vv, str):
				mm = re.search(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}期?|更新至\s*\d+\s*集|\d+\s*集全', vv)
				if mm: remark = mm.group(0); break
		seen.add(lid)
		items.append((title, lid, cover, remark, ''))
	return items

def _ysp_program_items(rawb):
	"""解析 program 响应 -> (节目列表, 命中方式)。
	三条路径按优先级, 互不干扰:
	  ① known   —— 纪录片/特别节目(program_cid_774/777)的标准结构, 旧代码写死的那套,
	                顶层 f2(data) -> f3(条目) -> f4/cid f5/title f8/cover, 一次命中。
	  ② adaptive —— 递归整棵树, 拒掉配置映射层。
	  ③ library  —— 容错线性扫描, 专治电视栏目两段式/顶层非标准/换行污染的响应。
	★为什么只有电视栏目坏: 它走 d11=program_library, 官网把「筛选枚举字典」和
	  「节目列表」塞进同一棵树, 且节目用纯数字 lid + f5 标题(不是 f4 cid); 而
	  纪录片/特别节目是纯节目列表、字段编号恰好与 ① 吻合, 所以一直正常。"""
	items, seen = [], set()
	rejected = [0]
	def add(fields):
		it = _ysp_item_from_fields(fields)
		if it and it[1] not in seen:
			seen.add(it[1]); items.append(it)
		elif not it:
			rejected[0] += 1
	# ① 已知结构优先(纪录片/特别节目走这条, 最快最准)
	try:
		top = _YspPB(rawb).read()
		for data_f in [v for f, wt, v in top if f == 2 and wt == 2]:
			for f, wt, v in _YspPB(data_f).read():
				if f == 3 and wt == 2:
					add(_YspPB(v).read())
	except Exception:
		pass
	if items:
		_ysp_diag('parse', 'known 结构命中 %d 条, 拒绝非节目层 %d' % (len(items), rejected[0]))
		return items, 'known'
	# ② 自适应: 递归找所有「中文标题 + 真cid」的消息
	for depth, fields in _ysp_pb_walk(rawb):
		add(fields)
	if items and all(it[0] in _YSP_CFG_TITLE for it in items):
		_ysp_diag('parse', '整页结果疑似分类映射表, 全部丢弃 -> 继续走 library 容错扫描')
		items = []
	if items:
		_ysp_diag('parse', 'adaptive 命中 %d 条, 拒绝非节目层 %d' % (len(items), rejected[0]))
		return items, 'adaptive'
	# ③ 电视栏目专用容错扫描(顶层错位/两段式/换行污染都能捞出来)
	lib = _ysp_library_items(rawb)
	if lib:
		_ysp_diag('parse', 'library 容错扫描命中 %d 条 (前两条=%s)' % (len(lib), lib[:2]))
		return lib, 'library'
	_ysp_diag('parse', '三路径均无节目: adaptive 拒绝 %d 层, library=0' % rejected[0])
	return [], 'none'

def _ysp_pb_total(rawb):
	"""只在外层(data 层)找总数, 不深入节目条目 —— 否则会把集数/时间戳误当 total,
	导致"明明到底了还一直翻页"。"""
	best = 0
	for depth, fields in _ysp_pb_walk(rawb):
		if depth > 2:
			continue
		for fn, wt, v in fields:
			if wt == 0 and isinstance(v, int) and 24 <= v < 200000:
				best = max(best, v)
	return best

def _ysp_program_once(cfg, filterValue, page, size):
	"""按给定配置发一次 program 请求 -> (items, total, err)。
	签名公式已用 HAR 真实 body 验证: md5(按key排序拼接 body) -> yspsdkinput。"""
	import ssl
	tag, url, appid, referer, origin, ua, sig_domain, sig_appid = cfg
	token = _ysp_get_token(cfg)
	if not token:
		return [], 0, 'token'
	body = {"filterValue":filterValue, "page":page, "pageSizeT":size}
	pairs = ["%s=%s" % (k, urllib.parse.unquote(str(body[k]))) for k in sorted(body.keys())]
	ysp  = _hl.md5("&".join(pairs).encode()).hexdigest()
	_YSP_SEQID[0] += 1
	seq  = str(_YSP_SEQID[0])
	reqid = "999999" + _ysp_prs(10) + str(int(time.time()*1000))
	input_str = "%s-%s-%s-%s" % (ysp, _YSP_PGUID, seq, reqid)
	raw  = "%s;%s;%s;https:;%s;%s;" % (_YSP_PGUID, sig_domain, token, sig_appid, input_str)
	sign = _hl.md5(raw.encode()).hexdigest() + "-" + input_str
	hdr = {"Accept":"application/json, text/plain, */*","Content-Type":"application/json",
	       "yspappid":appid,"platform":"109","app-platform":"pc","app-version":"1.0.0",
	       "yspsdkinput":ysp,"yspsdksign":sign,"seqId":seq,"request-id":reqid,
	       "User-Agent":ua,"Referer":referer,"Origin":origin}
	if tag == 'm':
		hdr['Cookie'] = _YSP_PCOOKIE
	ctx = ssl._create_unverified_context()
	try:
		r = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdr, method='POST'), timeout=8, context=ctx)
		rawb = r.read()
	except Exception as e:
		return [], 0, type(e).__name__
	items, how = _ysp_program_items(rawb)
	total = _ysp_pb_total(rawb)
	_ysp_diag('program', 'cfg=%s page=%s size=%s fv=%s bytes=%d parse=%s items=%d total=%s first=%s' %
	          (tag, page, size, filterValue, len(rawb), how, len(items), total, items[:1]))
	return items, total, ''

# 分类页结果缓存: 60s, 避免反复进出分类页重复打官网(性能修复)
_YSP_PROG_CACHE = {}

def _ysp_program(filterValue, page=1, size=24):
	"""央视频 program 分类接口 -> (items, has_more, total)。
	★三个页签统一走官网接口, 筛选条件经 filterValue 原样透传, 不再用静态清单裁剪。
	★按 HAR 修正: 优先 PC 配置(omsot / 519748109 / yangshipin.cn), 失败回退原 M 配置。
	★HAR 里官网是 pageSizeT=1、page 逐条递增(7,8,9,10…)。插件需要按页聚合,
	  故先按 size 请求; 只要返回不足一页(含真实响应只给 1 条的逐条情形), 就按官网
	  原样 pageSizeT=1 逐条补齐到一页。纪录片/特别节目通常单次即满, 不受影响。
	★分页: 本页满 size 条才继续下拉, 未满即到底。"""
	# ★★【分类页极其缓慢/加载失败 根因修复 · 本轮核心】
	#   旧逻辑: 「不足一页就逐条补齐」会跑 3 组配置 × 24 条 = 最多 72 次串行 POST,
	#   每次都要取 token + 算签名 + 20s 超时。官网一限流/网络一抖, 首页和分类页
	#   就转几十秒甚至直接失败 —— 这正是用户本轮反馈的问题, 与取流清晰度无关。
	#   ① 按 (filterValue, page, size) 做 60s 结果缓存, 反复进出分类页不再打官网;
	#   ② 逐条补齐硬上限 8 次, 且只用【已生效】的那组配置, 不再 3 组全试;
	#   ③ 连续 2 次空结果立即停止(限流/到底), 绝不空转; 上限仍为 size=24 条(保住节目全量);
	#   ④ 单次请求超时 20s -> 8s, 卡住最多 8s 而不是 20s。
	import time as _t
	_ck = (filterValue, page, size)
	_c = _YSP_PROG_CACHE.get(_ck)
	if _c and _t.time() - _c['ts'] < 60 and _c['items']:
		return list(_c['items']), _c['more'], _c['total']
	items, total, err = [], 0, ''
	_ok_cfg = None
	for cfg in _YSP_API_CFG:
		items, total, err = _ysp_program_once(cfg, filterValue, page, size)
		if items:
			_ok_cfg = cfg
			_ysp_diag('cfg', '生效配置 = %s (%s)' % (cfg[0], cfg[1]))
			break
	if len(items) < size:
		# 上限 = size(24 条), 保住「节目显示不全」的修复; 防卡靠的是下面三重:
		#   只用一组配置 / 连续2次空即停 / 单次8s超时, 不靠砍数量。
		# ★若 size 请求整页为空(官网只吃 pageSizeT=1), 也用首组配置逐条补齐,
		#   不再直接掉离线兜底 —— 这才是 HAR 里官网逐条滚动的真实行为。
		_fill_cfg = _ok_cfg or _YSP_API_CFG[0]
		start = (page - 1) * size + 1
		agg = list(items)
		seen = set(it[1] for it in items)
		calls, streak = 0, 0
		for p in range(start, start + size):
			if calls >= size or len(agg) >= size:
				break
			calls += 1
			one, _, _ = _ysp_program_once(_fill_cfg, filterValue, p, 1)
			if not one:
				streak += 1
				if streak >= 2:
					break
				continue
			streak = 0
			for it in one:
				if it[1] not in seen:
					seen.add(it[1]); agg.append(it)
		items = agg
		_ysp_diag('cfg', '生效配置 = %s (pageSizeT=1 逐条聚合) 补齐%d次 -> %d条' % (_fill_cfg[0], calls, len(items)))
	if not items:
		_ysp_diag('program', '所有配置均无数据 fv=%s err=%s' % (filterValue, err))
	has_more = len(items) >= size
	if total > 0 and total <= page * size:
		has_more = False
	_YSP_PROG_CACHE[_ck] = {'items': list(items), 'more': has_more,
	                        'total': total, 'ts': _t.time()}
	return items, has_more, total

def _ysp_title_to_vid(title):
	albs=_ysp_search(title)
	if not albs: return None
	cands=[a for a in albs if a["title"] and "快看" not in a["title"] and "星推荐" not in a["title"] and len(a["vids"])>=3]
	if not cands: cands=albs
	best=max(cands, key=lambda a: len(a["vids"]))
	if not best["vids"]: return None
	return best["vids"][0]["vid"]

def _ysp_best_album(title):
	"""剧名 -> 最佳全集专辑(直接取App搜索接口返回的全集真实vid列表, 绕开guid映射链路)。
	返回 {'cid','title','vids':[(ep,vid),...]} 或 None。
	剔除快看/星推荐等衍生噪点;
	修复: ①title若带" 子单元名"(如"奇迹 闯南关")先用主剧名(空格前)重试搜索;
	      ②选专辑时优先title与主剧名精确匹配, 避免误选集数更多的同名衍生专辑。"""
	base = title.strip()
	# 剥离子单元名: 取第一个空格前的部分作主剧名(对"奇迹 闯南关"->"奇迹")
	main = base.split(' ')[0].strip() if ' ' in base else base
	search_terms = [base]
	if main and main != base:
		search_terms.append(main)
	albs = []
	for t in search_terms:
		try:
			r = _ysp_search(t, size=30)
			if r:
				albs.extend(r)
		except Exception:
			pass
	# 若仅靠主剧名搜到结果(更精准), 丢弃带子单元名的搜索结果
	if main != base and albs:
		try:
			main_albs = _ysp_search(main, size=30)
			if main_albs:
				albs = main_albs
		except Exception:
			pass
	if not albs:
		return None
	cands = [a for a in albs if a["title"] and "快看" not in a["title"] and "星推荐" not in a["title"] and len(a["vids"]) >= 2]
	if not cands:
		# ≪方案A≫ App 搜索只返回 1 集新闻/科教噪点(如汪汪队→《科学动物园》/嗨芽儿/23号牛乃唐/熊出没),
		#   说明该剧在 App 并无全集专辑。此时绝不再回退选 1 集噪点(否则各季都误显示同一 1 集专辑),
		#   而是如实返回 None → detailContent 视为无可用源, 不造假数据。
		return None
	if not cands:
		return None
	# 名称最接近优先(优先title与主剧名完全一致/前缀一致), 其次有效集数、总集数
	def _score(a):
		t = (a["title"] or "").strip()
		nvalid = len([v for v in a["vids"] if v["vid"] and v["ep"]])
		ntotal = len(a["vids"])
		for term in (base, main):
			if not term:
				continue
			if t == term:
				return (10, nvalid, ntotal)
			if t.startswith(term):
				return (8, nvalid, ntotal)
		# 剔除词不相关(如"星卡梦少女 5:奇迹绽放"仅含衍生字样)再按集数
		return (0, nvalid, ntotal)
	best = max(cands, key=_score)
	if not best["vids"]:
		return None
	return best

def _ysp_fetch_state(url):
	"""请求央视频详情页, 解析并返回 __STATE_video__ JSON(或None)。"""
	import ssl
	ctx = ssl._create_unverified_context()
	hdr = {'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'}
	try:
		req = urllib.request.Request(url, headers=hdr)
		raw = urllib.request.urlopen(req, timeout=15, context=ctx).read().decode('utf-8','replace')
	except Exception:
		return None
	idx = raw.find('__STATE_video__')
	if idx < 0:
		return None
	idx = raw.find('{', idx)
	if idx < 0:
		return None
	depth = 0
	for i in range(idx, len(raw)):
		if raw[i] == '{': depth += 1
		elif raw[i] == '}':
			depth -= 1
			if depth == 0:
				try: return json.loads(raw[idx:i+1])
				except Exception: return None
	return None

def _ysp_guid_to_vid(guid):
	"""央视官网栏目guid(32位hex) -> 央视频vid。"""
	import urllib.request, ssl, json, re
	# 1) videoinfoByGuid 拿 title
	try:
		vurl = 'https://api.cntv.cn/video/videoinfoByGuid?guid=%s&serviceId=tvcctv' % guid
		req = urllib.request.Request(vurl, headers={'User-Agent':'Mozilla/5.0'})
		ctx = ssl._create_unverified_context()
		v = json.loads(urllib.request.urlopen(req, timeout=15, context=ctx).read().decode('utf-8','replace'))
	except Exception:
		return None
	title = v.get('title','')
	if not title:
		return None
	# 2) 提取栏目名(去掉《》/书名号/日期)
	date_m = re.search(r'(\d{8})', title)
	date = date_m.group(1) if date_m else ''
	core = re.sub(r'[《》]', '', title)
	core = re.sub(r'\d{8}', '', core).strip()
	colname = core.split(' ')[0] if core else core
	if not colname:
		return None
	# 3) search 拿"种子vid"(任意一期即可, 仅用于打开详情页)
	seed = None
	try:
		seed = _ysp_title_to_vid(colname)
	except Exception:
		seed = None
	# 4) 打开详情页拿 coverList(24期)
	cl = []
	if seed:
		js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&vid=%s' % seed)
		if js:
			pc = (js.get('payloads',{}) or {}).get('sharevideo',{}) or {}
			cl = pc.get('pastCover',{}) or {}
			cl = cl.get('coverList', []) or []
	# 5) 按日期精确匹配 cid —— 日期必须从 firstLine.text 提取!
	match_cid = None
	def _card_date(it):
		fl = (((it.get('poster',{}) or {}).get('poster',{}) or {}).get('firstLine',{}) or {}).get('text','') or ''
		m2 = re.search(r'(\d{8})', fl)
		return m2.group(1) if m2 else ''
	# 5a) 精确匹配(同日)
	for it in cl:
		cid = it.get('cid','')
		d = _card_date(it)
		if date and d == date:
			match_cid = cid
			break
	# 5b) 相邻日期容错(±1天)
	if not match_cid and date:
		cands = []
		for it in cl:
			d = _card_date(it)
			if d:
				try: cands.append((abs(int(d) - int(date)), it.get('cid','')))
				except Exception: pass
		if cands:
			cands.sort()
			if cands[0][0] <= 1:
				match_cid = cands[0][1]
	# 6) cid -> vid
	if match_cid:
		js2 = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s' % match_cid)
		if js2:
			vid = (js2.get('payloads',{}) or {}).get('sharevideo',{}) or {}
			vid = vid.get('vid','')
			if vid:
				return vid
	# 6.5) 聚合专辑全vid按日期匹配
	if date:
		try:
			ep_alb = _ysp_album_vids_by_title(colname)
		except Exception:
			ep_alb = None
		if ep_alb:
			for t, vid in ep_alb:
				m = re.search(r'(\d{8})', str(t))
				if m and m.group(1) == date and vid:
					return vid
	# 7) 回退: coverList 中栏目名一致的第一项
	if cl:
		for it in cl:
			fl = (((it.get('poster',{}) or {}).get('poster',{}) or {}).get('firstLine',{}) or {}).get('text','')
			if colname in re.sub(r'[《》]','', fl):
				cid = it.get('cid','')
				js2 = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s' % cid)
				if js2:
					vid = ((js2.get('payloads',{}) or {}).get('sharevideo',{}) or {}).get('vid','')
					if vid:
						return vid
				break
	# 8) 最终兜底: 沿用旧 search 逻辑
	try:
		albs = _ysp_search(colname, size=20)
	except Exception:
		albs = []
	for a in albs:
		if a['vids'] and colname in re.sub(r'[《》]','', a['title']):
			return a['vids'][0]['vid']
	# 9) ★影视剧全集映射兜底【核心修复】: 影视剧的guid title形如"《剧名》 第N集",
	#    无8位日期 -> 上方日期匹配全部失效, search直搜剧名也常返回0专辑(返回None)。
	#    正确路径: 用 _ysp_album_vids_by_title 拿全集真实vid列表, 按"第N集"集数精确匹配。
	#    (该函数对每日栏目按日期匹配不适用, 仅当无日期时才走此影视剧路径)
	if not date:
		_ep_m = re.search(r'第\s*(\d+)\s*集', title)
		if _ep_m:
			_ep_no = int(_ep_m.group(1))
			try:
				_ep_alb = _ysp_album_vids_by_title(colname)
			except Exception:
				_ep_alb = None
			if _ep_alb:
				# 9a) 优先: 按剧集标题里的数字精确匹配(标题可能为"1"/"第1集"/"01")
				for _t, _v in _ep_alb:
					_tm = re.search(r'(\d+)', str(_t))
					if _tm and int(_tm.group(1)) == _ep_no and _v:
						return _v
				# 9b) 兜底: ep_list按集数顺序排列, 直接按下标取(第N集 -> 索引N-1)
				if 1 <= _ep_no <= len(_ep_alb):
					_v = _ep_alb[_ep_no-1][1]
					if _v:
						return _v
	return None

def _ysp_album_vids_by_title(title):
	"""影视剧剧名 -> 央视频全集 [(集数title, vid), ...] 或 None。"""
	variants = [title]
	for ch in ['《','》','个','的','了']:
		variants.append(title.replace(ch, ''))
	t2 = title
	for ch in ['《','》','个','的','了']:
		t2 = t2.replace(ch, '')
	variants.append(t2)
	seen = []
	for x in variants:
		if x not in seen:
			seen.append(x)
	for t in seen:
		try:
			albs = _ysp_search(t)
		except Exception:
			albs = []
		if not albs:
			continue
		cands = [a for a in albs if a["title"] and "快看" not in a["title"] and "星推荐" not in a["title"] and len(a["vids"]) >= 3]
		if not cands:
			cands = albs
		best = max(cands, key=lambda a: len(a["vids"]))
		if not best["vids"]:
			continue
		seed = best["vids"][0]["vid"]
		js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&vid=%s' % seed)
		if not js:
			continue
		try:
			sv = js['payloads']['sharevideo']
			eps = sv.get('shareLongVideoRec', {}).get('episodes', {}).get('videoList', []) or []
		except Exception:
			continue
		ep_list = [(str(it.get('title') or '').strip(), it.get('vid')) for it in eps if it.get('vid')]
		if ep_list:
			return ep_list
		seed_title = (best.get('title') or title or '').strip()
		if seed and seed_title:
			return [(seed_title, seed)]
	return None

def _ysp_column_past_episodes(colname, max_items=36):
	"""央视每日栏目 -> 该栏目全部历史期次 [(期次标题, 真实vid), ...] (最新在前)。
	机制(完整复刻别人接口"电视栏目"): 搜索拿种子vid -> 打开种子详情页取
	pastCover.coverList(每期 cid=期次id) -> 逐期打开 detail 详情页(cid)拿真实vid。
	过滤: 期次标题须含栏目名(排除省级地方台同名栏目/搜索噪声)。
	注意: 该机制走央视频自身期次索引, 天然为央视内容(栏目都是CCTV各频道), 
	且 coverList 达22-25期含最新一期, 完美满足"取全取新"; 直接产出真实vid,
	播放走 get_ysp_mp4 取1080P优先(自动降级720P)的MP4直链。"""
	import re
	# 1) 搜索拿种子vid(任意一期即可, 仅用于打开种子详情页取过去期次)
	seed = None
	try:
		seed = _ysp_title_to_vid(colname)
	except Exception:
		seed = None
	if not seed:
		return []
	# 2) 打开种子详情页取 pastCover.coverList (全历史期次, 含最新一期)
	cl = []
	try:
		js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&vid=%s' % seed)
		if js:
			pc = (js.get('payloads',{}) or {}).get('sharevideo',{}) or {}
			cl = pc.get('pastCover',{}) or {}
			cl = cl.get('coverList', []) or []
	except Exception:
		cl = []
	if not cl:
		return []
	# 3) 逐期 cid -> 真实vid; 过滤标题不含栏目名的干扰项
	base = re.sub(r'[《》\s]','', colname)
	eps = []
	dup = set()
	for it in cl:
		cid = it.get('cid','')
		fl = (((it.get('poster',{}) or {}).get('poster',{}) or {}).get('firstLine',{}) or {}).get('text','') or ''
		if not cid:
			continue
		# 栏目名必须出现在期次标题中(排除地方台同名栏目/噪声)
		if base and base not in re.sub(r'[《》\s]','', fl):
			continue
		vid = None
		try:
			js2 = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s' % cid)
			if js2:
				vid = ((js2.get('payloads',{}) or {}).get('sharevideo',{}) or {}).get('vid','')
		except Exception:
			vid = None
		if vid and vid not in dup:
			dup.add(vid)
			eps.append((fl.strip() or cid, vid))
	# 4) 按期次日期倒序(最新在前)
	def _dk(it):
		m = re.search(r'(\d{8})', it[0])
		return m.group(1) if m else ''
	eps.sort(key=_dk, reverse=True)
	return eps[:max_items]

class Spider(Spider):  # 元类 默认的元类 type
	def getName(self):
		return "中央电视台"#可搜索
	def init(self,extend=""):
		global _YSP_DEBUG
		import os
		if (os.environ.get('YSP_DEBUG') == '1'
		    or 'debug' in str(extend).lower()):
			_YSP_DEBUG = True
		print("============{0}============".format(extend))
		if _YSP_DEBUG:
			print('[YSP] 诊断已开启: 将打印 program/playvinfo 响应结构; 排障后请去掉 extend 里的 debug')
		pass
	def destroy(self):
		pass
	def isVideoFormat(self,url):
		pass
	def manualVideoCheck(self):
		pass
	def homeContent(self,filter):
		result = {}
		# ★修复①: 只保留网站 /resource/pool 二级目录里的三个页签, 顺序严格为
		#   电视栏目 -> 纪录片 -> 特别节目; 电视剧/电影/动画片等一律不再输出。
		#   注意: 筛选行里的「全部」不是目录, 它就是「电视栏目」页签的默认态,
		#   由 self.config['filter']['电视栏目'][0] 原样保留, 不参与本次目录裁剪。
		result['class'] = [{'type_name': t, 'type_id': t} for t in _YSP_TABS]
		if(filter):
			result['filters'] = self.config['filter']
		# ★壳子首页「更新推荐」区块(截图里绿色背景那一栏): 主流壳子读
		#   homeContent()['list'] 渲染, 另一类壳子读 homeVideoContent()。
		#   两条协议都返回同一份「电视栏目」第一页, 共用缓存, 不重复请求、
		#   不新增第四个目录。卡片字段与分类页逐字一致, 点开即走同一条取流链路。
		result['list'] = self._ysp_home_recommend()
		return result
	# 首页「更新推荐」缓存: homeContent / homeVideoContent 每回首页都会调,
	# 官网 pageSizeT=1 模式下一页要逐条请求, 不缓存会明显拖慢首页。TTL 5 分钟。
	_YSP_HOME_CACHE = {"list": None, "ts": 0}
	def _ysp_home_recommend(self):
		"""生成壳子首页「更新推荐」列表 —— 直接复用「电视栏目」分类页第一页。
		★不新增目录: 三个二级目录仍只由 homeContent()['class'] 输出。
		★不改造卡片: 原样复用 categoryContent 的 vod_id / 封面 / vod_remarks,
		  所以点开就能走 prog~~~ 详情链路并继续 1080P 优先取流, 角标仍是官网动态期次。
		★默认「全部」+ 最新(sort=6), 即官网电视栏目按最新更新排序, 故名「更新推荐」。
		★取数失败时沿用上次缓存, 避免首页推荐位突然空白。"""
		now = time.time()
		cache = self._YSP_HOME_CACHE
		if cache["list"] and now - cache["ts"] < 300:
			return list(cache["list"])
		try:
			r = self.categoryContent('电视栏目', '1', True, {'datapa-sort': '最新'})
			rows = list(r.get('list') or [])
		except Exception:
			rows = []
		if rows:
			cache["list"] = rows
			cache["ts"] = now
		elif cache["list"]:
			_ysp_diag('home', '本次取数为空, 沿用上次缓存避免首页空白')
			return list(cache["list"])
		_ysp_diag('home', '更新推荐 复用电视栏目 pg1, 得到 %d 条' % len(rows))
		return rows
	def homeVideoContent(self):
		"""另一类壳子的首页推荐接口, 与 homeContent()['list'] 同源同缓存。
		title 供支持区块标题的壳子显示, 即截图里的「更新推荐」四个字。"""
		return {'list': self._ysp_home_recommend(), 'title': '更新推荐'}
	def _ysp_library_meta(self):
		"""逐栏目取 lid 详情页, 返回 {lid: (cover, 最新期次日期)}。
		★动态日期来源: __STATE_video__.payloads.sharevideo.pastCover.coverList[0]
		  .poster.poster.firstLine.text (如 "2026/11/21期"), 与官网卡片角标同源。
		并行 10 线程(原代码实测约 2.3s), 结果缓存; 单栏目失败只留空, 绝不拖垮整个列表,
		也绝不回退到静态清单里写死的旧日期。"""
		if not hasattr(self, '_ysp_lib_cache'):
			self._ysp_lib_cache = {}
		missing = [r for r in _YSP_COLUMNS if r[0] not in self._ysp_lib_cache]
		if missing:
			from concurrent.futures import ThreadPoolExecutor
			def fetch(row):
				lid = row[0]
				try:
					js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&lid=%s' % lid)
					cl = ((((js or {}).get('payloads',{}) or {}).get('sharevideo',{}) or {})
					      .get('pastCover',{}) or {}).get('coverList',[]) or []
					if cl:
						pp = ((cl[0].get('poster',{}) or {}).get('poster',{}) or {})
						cover = (pp.get('imageUrl') or '').split('/1080?')[0]
						fl = str((pp.get('firstLine',{}) or {}).get('text') or '').strip()
						date = _ysp_date_issue(fl)
						return (lid, (cover, date))
				except Exception:
					pass
				return (lid, ('', ''))
			with ThreadPoolExecutor(max_workers=10) as ex:
				for lid, meta in ex.map(fetch, missing):
					self._ysp_lib_cache[lid] = meta
			# 同步给 detailContent 用的封面缓存(保持其原有取值方式不变)
			self._ysp_cov_cache = {k: v[0] for k, v in self._ysp_lib_cache.items()}
		return self._ysp_lib_cache

	def _ysp_library_content(self, pg, extend):
		"""【离线兜底, 非数据源】仅在 program 接口完全失败时调用, 避免整页空白。
		静态 50 栏目 + 实时封面/日期; 24 条/页精确分页; 17 项频道筛选与排序本地生效。
		正常情况一律走 _ysp_program_content / program 接口拿官网全量数据。"""
		meta = self._ysp_library_meta()
		cat = _ysp_extval(extend, 'datafl-sc')
		sort = _ysp_extval(extend, 'datapa-sort')
		# 旧壳子/老收藏可能传来历史标识或非法筛选值, 一律视为「全部」
		if cat not in _YSP_LIBRARY_ITYPE_ORDER:
			cat = _YSP_COLUMN_ALL
		rows = list(_YSP_COLUMNS)
		if cat != _YSP_COLUMN_ALL:
			rows = [r for r in rows if _YSP_LIB_ITYPE.get(r[0]) == cat]
		if sort == '最热':
			# 有实时期次的按日期倒序(最近更新在前), 无日期的保持清单原序
			rows.sort(key=lambda r: meta.get(r[0], ('', ''))[1], reverse=True)
		SIZE = 24
		p = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
		chunk = rows[(p - 1) * SIZE: p * SIZE]
		videos = []
		for lid, name, cid, _ in chunk:
			cover, date = meta.get(lid, ('', ''))
			videos.append({
				'vod_id': 'library~~~%s~~~%s' % (lid, cid),
				'vod_name': self._strip_title_marks(name),
				'vod_pic': cover,
				'vod_remarks': date or ''
			})
		end = p * SIZE >= len(rows)
		return {
			'list': videos,
			'page': p,
			'pagecount': (p if end else 9999),
			'limit': SIZE,
			'total': len(rows)
		}

	def categoryContent(self,tid,pg,filter,extend):
		# 【健壮性】extend 可能被壳子以字符串传入(非dict), 统一转成dict
		if not isinstance(extend, dict):
			try:
				extend = json.loads(extend) if isinstance(extend, str) and extend else {}
			except Exception:
				extend = {}
		# 官网已统一改名为「电视栏目」: 除纪录片/特别节目外, 任何历史遗留或未知的
		#   type_id 一律归一到「电视栏目」, 老收藏不会变空列表, 文件里也不再保留旧称。
		tid = _YSP_TAB_ALIASES.get(tid, tid)
		if tid not in _YSP_TABS:
			tid = '电视栏目'
		_pg = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
		# ★★依据官网 HAR 定稿: /resource/pool 的「电视栏目」走
		#   POST csapi.yangshipin.cn/voapi/omsot/media/v2/program,
		#   filterValue=d11=program_library&itype=<频道>&sort=<排序>, 服务端返回全量并分页。
		#   旧 py 的 50 条静态清单只是抓包快照(且 HAR 里仅封面就出现 58 个不同 lid),
		#   "全部"和筛选都不全 —— 已降级为接口彻底失败时的离线兜底, 不再是数据源。
		#   接口端点/appid/Referer 等 4 处硬差异见 _YSP_API_CFG 注释。
		_pcid = _YSP_PROG_CID.get(tid, '')
		if not _pcid:
			return {'list': [], 'page': _pg, 'pagecount': _pg, 'limit': 24, 'total': 0}
		_SIZE = 24  # 插件每页展示 24 条(官网滚动加载为逐条, 由 _ysp_program 内部聚合)
		_fv = _ysp_fv_candidates(_pcid, tid, extend)[0]
		_progs, _has_more, _total = _ysp_program(_fv, page=_pg, size=_SIZE)
		if not _progs:
			_ysp_diag('fallback', 'program 接口无数据 fv=%s, 启用离线清单兜底' % _fv)
			return self._ysp_library_content(_pg, extend)
		videos = []
		for _title, _cid, _cover, _rem, _brief in _progs:
			# ★★【真机「暂无播放数据」根因修复 · 本轮核心】
			#   电视栏目(program_library)接口条目给的是【纯数字栏目的 lid】(如 10492),
			#   不是节目 cid。此前按纪录片/特别节目那样生成 prog~~~<lid>~~~... ,
			#   detailContent 的 prog 分支会把这个 lid 当成 cid 去请求
			#   video?type=0&cid=10492 -> 拿不到 __STATE_video__ -> 选集全空 -> return {}
			#   -> 壳子转圈约 10s 后显示「暂无播放数据」。这与取流清晰度完全无关,
			#   前几轮一直改 get_ysp_mp4 是找错了方向。
			#   用户最初上传的原文件用静态清单, 卡片正是 library~~~<lid>~~~<栏目cid>,
			#   detailContent 有专门分支用 video?type=0&lid=<lid> 取 pastCover.coverList
			#   产 "期次$~~~<期次cid>" -> playerContent 解析真实 vid -> MP4 直链, 实测可播。
			#   ✅ 保留官网接口的全量内容/筛选/动态日期/封面, 只把 vod_id 格式恢复到已验证链路。
			_vod_id = "prog~~~%s~~~%s~~~%s" % (_cid, _title, _cover)
			if tid == '电视栏目':
				_lid = str(_cid)
				if not re.fullmatch(r'\d{4,8}', _lid):
					# 万一解析到的是真实栏目 cid 字符串, 按栏目名反查静态表拿 lid
					for _k, _v in _YSP_COLUMNS_MAP.items():
						if _v[0] == _title:
							_lid = _k
							break
				if re.fullmatch(r'\d{4,8}', _lid):
					_row = _YSP_COLUMNS_MAP.get(_lid)
					_realcid = _row[1] if _row else _lid
					_vod_id = 'library~~~%s~~~%s' % (_lid, _realcid)
			# ★修复④: vod_remarks 用接口返回的真实最新期次/更新状态, 不再用静态清单里写死的日期
			videos.append({
				"vod_id": _vod_id,
				"vod_name": self._strip_title_marks(_title),
				"vod_pic": _cover,
				"vod_remarks": _rem
			})
		# ★修复③: 旧代码 pageSizeT=50(实际被截断成24)却按 50 判定"本页未满=到底",
		#   壳子第一页后就停止下拉 -> 节目显示不全。现按网站真实页大小取数,
		#   并以接口返回的 has_more/total 决定 pagecount, 未满页才终止, 满页继续翻。
		return {
			'list': videos,
			'page': _pg,
			'pagecount': (9999 if _has_more else _pg),
			'limit': _SIZE,
			'total': _total or (_pg * _SIZE + (1 if _has_more else 0))
		}
	def detailContent(self,array):
		result={}
		# 【电视栏目·播放链路】壳子把 categoryContent 返回的三段式 vod_id(library~~~<lid>~~~<cid>)
		#   原样作为 ids[0] 传入, 不会用 ### 或任何分隔符预拆。此处优先识别 library~~~ 三段式:
		#   从 _YSP_COLUMNS_MAP 反查栏目名, 设置 tid='电视栏目' 走对应分支, 避免 aid[3] 越界崩溃。
		_raw0 = array[0]
		if isinstance(_raw0, str) and _raw0.startswith('library~~~'):
			_parts = _raw0.split('~~~')
			_lid = _parts[1] if len(_parts) > 1 else ''
			_cid = _parts[2] if len(_parts) > 2 else ''
			_row = _YSP_COLUMNS_MAP.get(_lid)
			tid = '电视栏目'
			title = self._strip_title_marks(_row[0]) if _row else ''
			logo = (self._ysp_cov_cache or {}).get(_lid, '') if hasattr(self, '_ysp_cov_cache') else ''
			id = 'library~~~%s~~~%s' % (_lid, _cid)
			vod_year = ''
			actors = ''
			brief = _row[2] if _row else ''
			lastVideo = ''
			_is_library = True   # 供下方跳过无效的 videoinfoByGuid 回退(减少约 10s 转圈)
		elif isinstance(_raw0, str) and _raw0.startswith('prog~~~'):
			# 【program分类·方案A】categoryContent 返回的 vod_id: prog~~~<cid>~~~<title>~~~<cover>
			#   <cid> 为央视频节目库的节目cid。全集解析在下方 try 块 prog 专用分支用 cid 精确取,
			#   规避同名剧歧义, 每集"第N集$vid"播放串, fromId2='央视频' -> playerContent直接取MP4直链。
			_parts = _raw0.split('~~~')
			_pcid = _parts[1] if len(_parts) > 1 else ''
			_pname = _parts[2] if len(_parts) > 2 else ''
			_pcover = _parts[3] if len(_parts) > 3 else ''
			tid = '电视剧'  # 仅作类型标识; 全集解析由下方 prog 专用分支接管
			title = self._strip_title_marks(_pname)
			logo = _pcover
			id = _pcid
			vod_year = ''
			actors = ''
			brief = ''
			lastVideo = ''
			_is_prog = True  # 供下方 try 块识别 prog 分类, 用 cid 精确取全集
		else:
			aid = _raw0.split('###')
			tid = aid[0] if len(aid) > 0 else ''
			logo = aid[3] if len(aid) > 3 else ''
			lastVideo = aid[2] if len(aid) > 2 else ''
			title = aid[1] if len(aid) > 1 else ''
			title = self._strip_title_marks(title)
			# ★【标题清爽化】剥离tid分类前缀: api.cntv.cn 返回的 title 本身带分类前缀
			#   (如"电视剧奇迹"/"电视剧人民的选择")。若不剥离, ①标题难看; ②致命:
			#   _ysp_best_album("电视剧奇迹") 在央视频App搜"电视剧奇迹"搜不到(App里叫"奇迹")
			#   导致回退CCTV guid老链路, 复发"奇迹选集不全"。剥成纯剧名"奇迹"即可命中App全集。
			if tid and title and title.startswith(tid) and title != tid:
				_rest = title[len(tid):].strip()
				if _rest:
					title = _rest
			id = aid[4] if len(aid) > 4 else ''
			vod_year = aid[5] if len(aid) > 5 else ''
			actors = aid[6] if len(aid) > 6 else ''
			brief = aid[7] if len(aid) > 7 else ''
		fromId='CCTV'
		Url=''
		if tid=="电视栏目" and not locals().get('_is_library'):
			# ★library~~~ 三段式不是 32位hex guid, 拿它请求 videoinfoByGuid 必然无效且耗时;
			#   期次解析在下方 1867 行分支用 lid 独立完成, 这里整体跳过以消除转圈。
			# 【电视栏目】新逻辑改走"栏目名->pastCover.coverList->cid->真实vid",
			#   已不依赖 videoinfoByGuid 的 topicId; 此初始块仅作为回退时 Url 备用,
			#   故整体包进 try, 即使 guid 无效/接口异常也绝不阻塞主流程(否则整段崩溃)。
			try:
				lastUrl = 'https://api.cntv.cn/video/videoinfoByGuid?guid={0}&serviceId=tvcctv'.format(id)
				htmlTxt = self.webReadFile(urlStr=lastUrl,header=self.header)
				_j = json.loads(htmlTxt)
				topicId = _j.get('ctid')
				if topicId:
					Url = "https://api.cntv.cn/NewVideo/getVideoListByColumn?id={0}&d=&p=1&n=100&sort=desc&mode=0&serviceId=tvcctv&t=json".format(topicId)
					htmlTxt = self.webReadFile(urlStr=Url,header=self.header)
			except Exception:
				pass
		else:
			Url='https://api.cntv.cn/NewVideo/getVideoListByAlbumIdNew?id={0}&serviceId=tvcctv&p=1&n=100&mode=0&pub=1'.format(id)
		jRoot = ''
		videoList = []
		fromId2 = None
		try:
			if locals().get('_is_prog'):
				# 【program分类·取全集】以节目cid打开央视频详情页, 按网站真实结构分派:
				#   ① shareLongVideoRec.episodes.videoList -> 纪录片/特别节目(全集真实vid)
				#   ② pastCover.coverList -> 电视栏目按期次组织的栏目(每期cid, 产 ~~~cid)
				#   ③ 剧名搜索最佳全集专辑兜底  ④ 顶层 vid 单集兜底
				# ★四种产出统一 fromId2='央视频': ①③的vid直接 get_ysp_mp4 取1080P优先(自动降级720P)的MP4直链;
				#   ②的 ~~~cid 由 playerContent 先解析成真实vid再取1080P优先的直链, 播放能力不变。
				videoList=[]
				fromId2='央视频'
				_seen=set()
				_sv={}
				try:
					_js=_ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s'%id)
					if _js:
						_sv=(_js.get('payloads',{}) or {}).get('sharevideo',{}) or {}
				except Exception:
					_sv={}
				# ① 剧集/纪录片/特别节目: 全集 episodes
				try:
					_eps=((_sv.get('shareLongVideoRec',{}) or {}).get('episodes',{}) or {}).get('videoList',[]) or []
					for _it in _eps:
						_vid=_it.get('vid')
						_tt=str(_it.get('title') or '').strip()
						if _vid and _vid not in _seen:
							_seen.add(_vid)
							if not _tt or not _tt.startswith('第'):
								_tt='第%d集'%len(_seen)
							videoList.append('%s$%s'%(_tt,_vid))
				except Exception:
					pass
				# ② 电视栏目: pastCover.coverList 历史期次(最新在前)
				if not videoList:
					try:
						_cl=((_sv.get('pastCover',{}) or {}).get('coverList',[]) or [])
						for _it in _cl:
							_cid=_it.get('cid')
							_t=str((((_it.get('poster') or {}).get('poster') or {}).get('firstLine') or {}).get('text') or '').strip()
							if not _t: _t=str(_it.get('num') or '')
							if _cid and _cid not in _seen:
								_seen.add(_cid)
								videoList.append('%s$~~~%s'%(_t or _cid, _cid))
					except Exception:
						pass
				# ③ 兜底: 剧名搜索最佳全集专辑
				if not videoList:
					try:
						_aa=_ysp_best_album(title)
					except Exception:
						_aa=None
					if _aa and _aa.get('vids'):
						_epi=0
						for _e,_v in _aa['vids']:
							_vid=_v.get('vid')
							if not _vid: continue
							_epi+=1
							_en=str(_e).strip() if _e else ''
							if not _en or not _en.startswith('第'):
								_en='第%d集'%_epi
							if _vid not in _seen:
								_seen.add(_vid)
								videoList.append('%s$%s'%(_en,_vid))
				# ④ 单集兜底(如"2026开学第一课"): sharevideo 顶层 vid
				if not videoList:
					_top_vid = _sv.get('vid','')
					if _top_vid and _top_vid not in _seen:
						_tt2 = str(_sv.get('title') or '').strip() or title
						_seen.add(_top_vid)
						videoList.append('%s$%s'%(_tt2,_top_vid))
			elif tid=="搜索":
				# 【问题④修复】搜索的央视网页短视频(如"秘境之眼")仅提供HLS线路, 壳子EXO对其
				#   AAC-LC(48000Hz)音频轨AudioTrack直通初始化失败(AUDIO_TRACK_INIT_FAILED)导致
				#   播放中断/不足2分钟。这里抓取网页提取32位hex guid作为播放id, 让playerContent
				#   命中32位hex guid分支: _ysp_guid_to_vid映射央视频vid -> get_ysp_mp4取1080P优先(自动降级720P)的MP4直链,
				#   彻底绕开HLS音频直通bug, 同时满足720P以上+可拖进度条。
				fromId='中央台'
				_m = None
				try:
					_ph = self.webReadFile(urlStr=lastVideo, header=self.header)
					_m = re.search(r'var\sguid\s*=\s*"([0-9a-f]{32})"', _ph) or \
					     re.search(r'([0-9a-f]{32})', _ph)
				except Exception:
					_m = None
				if _m:
					# 用guid作播放id, playerContent走MP4映射分支
					videoList=[title+"$"+_m.group(1)]
				else:
					# 抓不到guid时回退原逻辑(webReadFile抓取提取)
					videoList=[title+"$"+lastVideo]
			else:
				if tid=="电视栏目":
					# 【电视栏目·完整复刻别人机制】解析三段式 library~~~<lid>~~~<cid> 取 lid,
					#   调 video?type=0&lid= 取 pastCover.coverList(25期含最新) -> 产"期次标题$~~~<cid>"。
					#   与别人detailContent返回完全一致: 播放串id=~~~<cid>, playerContent剥离~~~后
					#   取详情页真实vid -> get_ysp_mp4 取1080P优先(自动降级720P)的MP4直链(实测0.4s成功)。
					videoList=[]
					fromId2='央视频'
					_seen=set()
					_lid=None
					_mm=re.match(r'library~~~(\d+)~~~', str(id)) or re.match(r'^(\d+)$', str(id))
					if _mm: _lid=_mm.group(1)
					# ★不再要求 lid 必须存在于旧静态清单: 官网接口返回的新栏目同样可播
					if _lid:
						try:
							_js=_ysp_fetch_state('https://m.yangshipin.cn/video?type=0&lid=%s'%_lid)
							if _js:
								_sv=(_js.get('payloads',{}) or {}).get('sharevideo',{}) or {}
								_cl=((_sv.get('pastCover',{}) or {}).get('coverList',[]) or [])
								for _it in _cl:
									_cid=_it.get('cid')
									_t=''
									try:
										_t=str((((_it.get('poster') or {}).get('poster') or {}).get('firstLine') or {}).get('text') or '').strip()
									except Exception:
										_t=''
									if not _t: _t=str(_it.get('num') or '')
									if _cid and _t and _cid not in _seen:
										_seen.add(_cid)
										videoList.append('%s$~~~%s'%(_t,_cid))
						except Exception:
							videoList=[]
					# 次级兜底: lid机制失效(如新栏目不在静态清单) -> 旧"栏目名->pastCover->真实vid"链路
					if not videoList:
						try:
							_past = _ysp_column_past_episodes(title)
						except Exception:
							_past = []
						if _past:
							_seen=set()
							for _t,_v in _past:
								if _v and _v not in _seen:
									_seen.add(_v)
									videoList.append("%s$%s"%(_t,_v))
					# 兜底: 若期次链路为空, 回退原App搜索按期次收集每期真实vid
					if not videoList:
						try:
							_albs = _ysp_search(title) or []
							_base = re.sub(r'[《》\s]','', title)
							_seen=set()
							for _a in _albs:
								_t=str(_a.get('title') or '').strip()
								_vids=_a.get('vids') or []
								if not _vids: continue
								_tt=re.sub(r'[《》\s]','', _t)
								if not _base or _base not in _tt:
									continue
								_is_bare = (len(_vids)>1) and (_tt==_base or not re.search(r'\d{6,8}|第\d+集|：|:',_t))
								if _is_bare:
									_ep_list=[]
									_seed=_vids[0].get('vid')
									if _seed:
										try:
											_st=_ysp_fetch_state('https://m.yangshipin.cn/video?type=0&vid=%s'%_seed)
											_sv=_st['payloads']['sharevideo']
											_eps=_sv.get('shareLongVideoRec',{}).get('episodes',{}).get('videoList',[]) or []
											_ep_list=[(str(it.get('title') or '').strip(), it.get('vid')) for it in _eps if it.get('vid')]
										except Exception:
											_ep_list=[]
									if _ep_list:
										for _et,_ev in _ep_list:
											if _ev and _ev not in _seen:
												_seen.add(_ev)
												videoList.append("%s$%s"%(_et,_ev))
										continue
								for _vv in _vids:
									_vid=_vv.get('vid')
									if _vid and _vid not in _seen:
										_seen.add(_vid)
										videoList.append("%s$%s"%(_t,_vid))
						except Exception:
							videoList=[]
				# ===== 【按App重写】影视剧类(电视剧/动画片/纪录片/特别节目)优先用"央视频"App数据流 =====
				# 直接以剧名调 App 同源搜索接口(csapi.yangshipin.cn)拿全集真实vid列表,
				#   绕开"网页guid->搜索映射vid"脆弱链路。
				_app_album = None
				if tid in ("电视剧","动画片","纪录片","特别节目"):
					try:
						_app_album = _ysp_best_album(title)
					except Exception:
						_app_album = None
				if _app_album and _app_album.get('vids'):
					vids = [(item.get('ep'), item.get('vid')) for item in _app_album['vids'] if item.get('vid')]
					if vids:
						videoList = []
						_epi = 0
						for _e,_v in vids:
							_epi += 1
							_en = str(_e).strip() if _e else ''
							if not _en or not _en.startswith('第'):
								_en = '第%d集' % _epi
							videoList.append("%s$%s" % (_en, _v))
						fromId2 = '央视频'
				# ---- 回退: App数据流拿不到则走原guid链路(api.cntv.cn 列表 + 32位hex guid) ----
				if not videoList:
					htmlTxt=self.webReadFile(urlStr=Url,header=self.header)
					jRoot = json.loads(htmlTxt)
					data=jRoot['data']
					jsonList=data['list']
					# 【全分类统一】所有分类走央视频MP4映射模式
					# (lazy保留guid, 点播时playerContent按32位hex guid映射取1080P优先(自动降级720P)的MP4直链)
					videoList=self.get_EpisodesList(jsonList=jsonList, map_to_vid=True, lazy=True)
					if len(videoList)<1:
						htmlTxt=self.webReadFile(urlStr=lastVideo,header=self.header)
						if tid=="电视剧" or tid=="纪录片":
							patternTxt=r"'title':\s*'(?P<title>.+?)',\n{0,1}\s*'brief':\s*'(.+?)',\n{0,1}\s*'img':\s*'(.+?)',\n{0,1}\s*'url':\s*'(?P<url>.+?)'"
						elif tid=="特别节目":
							patternTxt=r'class="tp1"><a\s*href="(?P<url>https://.+?)"\s*target="_blank"\s*title="(?P<title>.+?)"></a></div>'
						elif tid=="动画片":
							patternTxt=r"'title':\s*'(?P<title>.+?)',\n{0,1}\s*'img':\s*'(.+?)',\n{0,1}\s*'brief':\s*'(.+?)',\n{0,1}\s*'url':\s*'(?P<url>.+?)'"
						elif tid=="电视栏目":
							patternTxt=r'href="(?P<url>.+?)" target="_blank" alt="(?P<title>.+?)" title=".+?">'
						videoList=self.get_EpisodesList_re(htmlTxt=htmlTxt,patternTxt=patternTxt)
						fromId='央视'
		except:
			pass
		if fromId2:
			fromId = fromId2
		if len(videoList) == 0:
			return {}
		vod = {
			"vod_id":array[0],
			"vod_name":title,
			"vod_pic":logo,
			"type_name":tid,
			"vod_year":vod_year,
			"vod_area":"",
			"vod_remarks":'',
			"vod_actor":actors,
			"vod_director":'',
			"vod_content":brief
		}
		vod['vod_play_from'] = fromId
		# ===== 【选集VIP标识·方案A·exem判据+顺序边界提效】仅对央视频点播流(影视剧App数据流
		#   fromId2=='央视频') =====
		# ★提效原理(经真实剧逐集验证): 免费集恒exem=0(paytype 879/vl=True), 付费集exem=2
		#   (paytype 880, 部分带试看vl故过期"有无vl"判据作废)。常见"前几集免费后面收费"边界
		#   (种墨园前2集免费/人民的选择全收费/西游记全免费均已实测), 故采用顺序探测:
		#   按集序逐集探测, 遇首个VIP集(第N集)后, 其后所有集默认标[VIP]并停止探测(边界后持续
		#   收费), 请求数从"全集数"降到"边界点", 收费剧O(1)/免费剧探满即停/混合剧O(边界点)。
		if fromId2 == '央视频' and videoList:
			import time as _t
			_vip_map = {}
			# 收集有序待测 央视频vid(形如 z0000459kta): 排除 32位hex 与 ~~~cid
			_candidates = []
			_ep_name = {}
			for _item in videoList:
				if '$' not in _item:
					continue
				_en, _v = _item.split('$', 1)
				_v = _v.strip()
				# 央视频vid: 1个字母开头+数字(如 z0000459kta / r000095lofp); 排除 32位hex 与 ~~~cid
				if not _v or _v.startswith('~~~') or not re.match(r'^[a-z]\d{4,}', _v):
					continue
				_candidates.append(_v)
				_ep_name[_v] = _en
			# 顺序探测: 逐集探测, 首个VIP后其后全部免探测默认VIP
			_found_vip = False
			_dl = time.time() if 'time' in dir() else _t.time()
			_ttl = 5.5  # join预算内完成探测
			for _v in _candidates:
				if _found_vip:
					_vip_map[_v] = True  # 首个VIP之后: 免探测, 默认VIP
					continue
				if _t.time() - _dl > _ttl:
					break  # 超时预算: 停止探测, 未探保持原名
				try:
					_vip_map[_v] = self._ysp_is_vip(_v)
				except Exception:
					_vip_map[_v] = None
				if _vip_map[_v] is True:
					_found_vip = True  # 首个VIP: 边界定, 其后默认全VIP
			# 重写 videoList: VIP集(判定为True)集名追加[VIP]
			_new_list = []
			for _item in videoList:
				if '$' not in _item:
					_new_list.append(_item); continue
				_en, _v = _item.split('$', 1)
				_v = _v.strip()
				if _v in _vip_map and _vip_map[_v] is True:
					_new_list.append("%s[VIP]$%s" % (_en, _v))
				else:
					_new_list.append(_item)
			videoList = _new_list
		vod['vod_play_url'] = "#".join(videoList)
		result = {
			'list':[
				vod
			]
		}
		return result
	def searchContent(self,key,quick,pg='1'):
		# 兼容壳子以 (key, quick, pg) 三参数调用; 缺省 pg 兼容旧式两参数调用
		return self.searchContentPage(key, quick, pg or '1')
	def searchContentPage(self, key, quick, page):
		# 【搜索改造·央视频同源】放弃央视网网页搜索(search.cctv.com/ifsearch.php), 改走
		#   央视频官方搜索接口 csapi.yangshipin.cn/voapi/omsotm/v2/search, 与"电视剧/动画片/
		#   纪录片/特别节目/电影/电视栏目等分类完全同源、数据完全一致。返回 prog~~~<cid>~~~<title>
		#   四段式 vod_id —— detailContent 的 prog 专用分支用 cid 打开央视频详情页取全集真实vid,
		#   playerContent 直接 get_ysp_mp4 取1080P优先(自动降级720P)的MP4直链。至此壳子搜索与分类数据源完全统一。
		videos=[]
		try:
			_base = str(key).strip()
			if not _base:
				return {'list': videos}
			_albs = _ysp_search(_base, size=30) or []
			_seen=set()
			for _a in _albs:
				_cid=_a.get('cid') or ''
				_t=str(_a.get('title') or '').strip()
				if not _cid or not _t or _cid in _seen:
					continue
				_seen.add(_cid)
				_t = self._strip_title_marks(_t)
				_cov = _a.get('cover') or ''
				videos.append({
					"vod_id": "prog~~~%s~~~%s~~~%s" % (_cid, _t, _cov),
					"vod_name": _t,
					"vod_pic": _cov,
					"vod_remarks": '',
				})
		except Exception:
			videos=[]
		result = {
			'list':videos
		}
		return result
	def playerContent(self,flag,id,vipFlags):
		result = {}
		url=''
		parse=0
		headers = {
			'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'
		}
		# 【全分类统一央视频MP4直链】播放串里的id为32位hex guid(所有分类每集guid)时,
		#   精确映射为央视频vid -> get_ysp_mp4取1080P优先(自动降级720P)的MP4直链; 映射失败留空(绝不嗅探/不设parse=1)。
		#   电视栏目/电视剧/动画片/纪录片/特别节目分类的选集guid均为32位hex,统一由此接管。
		# 【按App重写】"央视频"播放源: 播放串里的id已是真实vid(如 x0000400dt9),
		#   直接get_ysp_mp4取确定性档位的MP4直链(vid为核心, 不再依赖guid映射)。
		# startswith 兼容上一版曾短暂用过的「央视频栏目」播放源名(老收藏/缓存)
		if isinstance(flag, str) and flag.startswith('央视频'):
			_cid_failed = False
			try:
				_iphone = {
					'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
					'Referer':'https://v.yangshipin.cn/'
				}
				# 【按App重写·电视栏目期次适配】播放串里的id可能为"~~~<cid>"格式
				#   (别人"电视栏目"分类的期次id, 如 ~~~skmna7n7ptliakk)。
				#   cid不是真实vid, 需先剥离"~~~"前缀, 打开 video?type=0&cid= 详情页
				#   取 sharevideo.vid 真实vid, 再 get_ysp_mp4 取1080P优先(自动降级720P)的MP4直链。
				_play_id = id
				# ★所有点播一律走官网同款 fhd 打头, 不再按分类/flag/id 前缀做任何档位分流。
				#   仅此处需要做的: ~~~<cid> 是栏目期次 cid, 先解析成真实 vid。
				if isinstance(_play_id, str) and _play_id.startswith('~~~'):
					_cid = _play_id[3:]
					# ★先查缓存: 同一期次后续播放直接用上次的真实 vid, 不再发详情页请求
					_real = _YSP_CID_VID_CACHE.get(_cid)
					if not _real:
						# ★解析偶发失败时重试 3 次(详情页偶发无 __STATE_video__),
						#   绝不把 cid 当 vid 交给取流接口
						for _attempt in range(3):
							try:
								_js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s' % _cid)
								if _js:
									_real = ((_js.get('payloads',{}) or {}).get('sharevideo',{}) or {}).get('vid','')
							except Exception:
								_real = None
							if _real:
								break
						if _real:
							_YSP_CID_VID_CACHE[_cid] = _real
							_ysp_diag('detail', 'cid=%s -> vid=%s 已缓存' % (_cid, _real))
						else:
							_ysp_diag('detail', '★cid=%s 解析真实 vid 失败(3次), 本次不取流' % _cid)
					if _real:
						_play_id = _real
					else:
						# 解析彻底失败: 不把 cid 冒充 vid(那样会拿到不可控档位), 直接放弃本次取流
						_play_id = None
						_cid_failed = True
				# 用 _play_id 取官网同款 fhd(1080P) 优先、自动降级 720P 的 MP4 直链
				try:
					cand = self.get_ysp_mp4(vid=_play_id) if _play_id else None
				except Exception:
					cand = None
				if cand and cand.startswith('http'):
					headers = _iphone
					url = cand
					result["format"] = 'video/mp4'
			except Exception:
				pass
			if not url:
				if _cid_failed:
					# 期次 cid 解析真实 vid 失败(非会员问题), 给准确提示而非误标 VIP
					url = "【取流失败】未能解析该期次的播放地址，请返回重进或稍后重试"
				else:
					# vid取流失败 -> 通常为央视频VIP付费内容, 给VIP标识而非静默黑屏
					url = "【VIP】该剧为央视频付费内容，请登录央视频官方APP/VIP账号观看"
				result["format"] = ''
		elif re.search(r'^[0-9a-f]{32}$', id):
			try:
				_iphone = {
					'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
					'Referer':'https://v.yangshipin.cn/'
				}
				_ysp_vid = _ysp_guid_to_vid(id)
				if _ysp_vid:
					cand = self.get_ysp_mp4(vid=_ysp_vid)
					if cand and cand.startswith('http'):
						headers = _iphone
						url = cand
						result["format"] = 'video/mp4'
			except Exception:
				pass
		result["parse"] = parse # 0=不嗅探/直链播放
		result["playUrl"] = ''
		result["url"] = url
		result["header"] =headers
		return result
	config = {
	"player": {},
	# 筛选 UI 由 _YSP_FILTER_MAP 直接生成, 只保留「电视栏目/纪录片/特别节目」三个页签,
	# 选项/顺序/枚举与官网一致。下方 _legacy 是旧版手写配置, 已废弃、壳子不读取。
	"filter": _ysp_filters_config(),
	"_deprecated_filters": {
	"电视剧":[{"key":"datafl-sc","name":"类型","value":[{"n":"历史","v":"历史"},{"n":"军事","v":"军事"},{"n":"武侠","v":"武侠"},{"n":"偶像","v":"偶像"},{"n":"爱情","v":"爱情"},{"n":"刑侦","v":"刑侦"},{"n":"古装","v":"古装"},{"n":"喜剧","v":"喜剧"},{"n":"奇幻","v":"奇幻"},{"n":"家庭","v":"家庭"},{"n":"悬疑","v":"悬疑"},{"n":"战争","v":"战争"},{"n":"剧情","v":"剧情"},{"n":"青春","v":"青春"},{"n":"神话","v":"神话"},{"n":"都市","v":"都市"},{"n":"农村","v":"农村"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"中国香港","v":"中国香港"},{"n":"中国台湾","v":"中国台湾"},{"n":"美国","v":"美国"},{"n":"英国","v":"英国"},{"n":"泰国","v":"泰国"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"动画片":[{"key":"datafl-sc","name":"类型","value":[{"n":"益智","v":"益智"},{"n":"冒险","v":"冒险"},{"n":"合家欢","v":"合家欢"},{"n":"竞技","v":"竞技"},{"n":"少年","v":"少年"},{"n":"真人","v":"真人"},{"n":"魔幻科幻","v":"魔幻科幻"},{"n":"战斗","v":"战斗"},{"n":"儿童故事","v":"儿童故事"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"日本","v":"日本"},{"n":"英国","v":"英国"},{"n":"欧美","v":"欧美"}]}],
	"纪录片":[{"key":"datafl-sc","name":"类型","value":[{"n":"文史","v":"文史"},{"n":"自然","v":"自然"},{"n":"美食","v":"美食"},{"n":"军事","v":"军事"},{"n":"科技","v":"科技"},{"n":"体育","v":"体育"},{"n":"健康","v":"健康"},{"n":"农业","v":"农业"},{"n":"旅游","v":"旅游"},{"n":"社会","v":"社会"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"日本","v":"日本"},{"n":"韩国","v":"韩国"},{"n":"英国","v":"英国"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"特别节目":[{"key":"datafl-sc","name":"类型","value":[{"n":"综艺","v":"综艺"},{"n":"资讯","v":"资讯"},{"n":"文史","v":"文史"},{"n":"教育","v":"教育"},{"n":"体育","v":"体育"},{"n":"社会","v":"社会"},{"n":"法治","v":"法治"},{"n":"自然","v":"自然"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"其他","v":"其他"}]}],
	"电影":[{"key":"datafl-sc","name":"类型","value":[{"n":"传记","v":"传记"},{"n":"伦理","v":"伦理"},{"n":"冒险","v":"冒险"},{"n":"武侠","v":"武侠"},{"n":"动作","v":"动作"},{"n":"爱情","v":"爱情"},{"n":"历史","v":"历史"},{"n":"喜剧","v":"喜剧"},{"n":"奇幻","v":"奇幻"},{"n":"战争","v":"战争"},{"n":"恐怖","v":"恐怖"},{"n":"悬疑","v":"悬疑"},{"n":"科幻","v":"科幻"},{"n":"犯罪","v":"犯罪"},{"n":"动画","v":"动画"},{"n":"励志","v":"励志"},{"n":"剧情","v":"剧情"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"中国香港","v":"中国香港"},{"n":"日本","v":"日本"},{"n":"英国","v":"英国"},{"n":"泰国","v":"泰国"},{"n":"印度","v":"印度"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"_legacy":[{"key":"cid","name":"频道","value":[{"n":"全部","v":""},{"n":"CCTV-1综合","v":"EPGC1386744804340101"},{"n":"CCTV-2财经","v":"EPGC1386744804340102"},{"n":"CCTV-3综艺","v":"EPGC1386744804340103"},{"n":"CCTV-4中文国际","v":"EPGC1386744804340104"},{"n":"CCTV-5体育","v":"EPGC1386744804340107"},{"n":"CCTV-6电影","v":"EPGC1386744804340108"},{"n":"CCTV-7国防军事","v":"EPGC1386744804340109"},{"n":"CCTV-8电视剧","v":"EPGC1386744804340110"},{"n":"CCTV-9纪录","v":"EPGC1386744804340112"},{"n":"CCTV-10科教","v":"EPGC1386744804340113"},{"n":"CCTV-11戏曲","v":"EPGC1386744804340114"},{"n":"CCTV-12社会与法","v":"EPGC1386744804340115"},{"n":"CCTV-13新闻","v":"EPGC1386744804340116"},{"n":"CCTV-14少儿","v":"EPGC1386744804340117"},{"n":"CCTV-15音乐","v":"EPGC1386744804340118"},{"n":"CCTV-16奥林匹克","v":"EPGC1634630207058998"},{"n":"CCTV-17农业农村","v":"EPGC1563932742616872"},{"n":"CCTV-5+体育赛事","v":"EPGC1468294755566101"}]},{"key":"fc","name":"分类","value":[{"n":"全部","v":""},{"n":"新闻","v":"新闻"},{"n":"体育","v":"体育"},{"n":"综艺","v":"综艺"},{"n":"健康","v":"健康"},{"n":"生活","v":"生活"},{"n":"科教","v":"科教"},{"n":"经济","v":"经济"},{"n":"农业","v":"农业"},{"n":"法治","v":"法治"},{"n":"军事","v":"军事"},{"n":"少儿","v":"少儿"},{"n":"动画","v":"动画"},{"n":"纪实","v":"纪实"},{"n":"戏曲","v":"戏曲"},{"n":"音乐","v":"音乐"},{"n":"影视","v":"影视"}]},{"key":"fl","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"}]},{"key":"year","name":"年份","value":[{"n":"全部","v":""},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"2004","v":"2004"},{"n":"2003","v":"2003"},{"n":"2002","v":"2002"},{"n":"2001","v":"2001"},{"n":"2000","v":"2000"}]},{"key":"month","name":"月份","value":[{"n":"全部","v":""},{"n":"12","v":"12"},{"n":"11","v":"11"},{"n":"10","v":"10"},{"n":"09","v":"09"},{"n":"08","v":"08"},{"n":"07","v":"07"},{"n":"06","v":"06"},{"n":"05","v":"05"},{"n":"04","v":"04"},{"n":"03","v":"03"},{"n":"02","v":"02"},{"n":"01","v":"01"}]}]
		}
	}
	header = {
		"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36",
		"Host": "tv.cctv.com",
		"Referer": "https://tv.cctv.com/"
	}
		
	def localProxy(self,param):
		return [200, "video/MP2T", ""]
	#-----------------------------------------------自定义函数-----------------------------------------------
	#访问网页
	def webReadFile(self,urlStr,header):
		html=''
		req=urllib.request.Request(url=urlStr)#,headers=header
		with  urllib.request.urlopen(req)  as response:
			html = response.read().decode('utf-8')
		return html
	#判断网络地址是否存在
	def TestWebPage(self,urlStr,header):
		html=''
		req=urllib.request.Request(url=urlStr,method='HEAD')#,headers=header
		with  urllib.request.urlopen(req)  as response:
			html = response.getcode () 
		return html
	#正则取文本
	def get_RegexGetText(self,Text,RegexText,Index):
		returnTxt=""
		Regex=re.search(RegexText, Text, re.M|re.S)
		if Regex is None:
			returnTxt=""
		else:
			returnTxt=Regex.group(Index)
		return returnTxt
	#取集数
	def get_EpisodesList(self,jsonList,map_to_vid=False,lazy=False,enc=False):
		# map_to_vid=True+lazy=True(电视栏目): 保留原始guid在播放串, 由 playerContent
		#   在点播那一刻再为该集单独精确映射取vid(guid->日期->cid->vid->get_ysp_mp4 1080P优先)。
		#   这样选集秒开 + 每集拿到各自独立vid(根治错台)。
		# enc=True(其他分类): 播放串编码 @@HD@@ 分类标记(改版方案B用; 本移植版默认不使用)。
		videos=[]
		for vod in jsonList:
			url = vod.get('guid','')
			title = vod.get('title','')
			if len(url) == 0:
				continue
			if map_to_vid and not lazy:
				try:
					v = _ysp_guid_to_vid(url)
					if v:
						url = v
				except Exception:
					pass
			title = self._strip_title_marks(title)
			# 统一去剧名前缀: 从"第N集"或日期处截取到结尾(电视剧/动画片/电视栏目均适用)
			title = self._clean_ep_title(title)
			if enc:
				videos.append(title+"$@@HD@@"+url)
			else:
				videos.append(title+"$"+url)
		return videos
	#取集数
	def get_EpisodesList_re(self,htmlTxt,patternTxt):
		ListRe=re.finditer(patternTxt, htmlTxt, re.M|re.S)
		videos=[]
		for vod in ListRe:
			url = vod.group('url')
			title =vod.group('title')
			if len(url) == 0:
				continue
			title = self._strip_title_marks(title)
			# 统一去剧名前缀: 从"第N集"或日期处截取到结尾
			title = self._clean_ep_title(title)
			videos.append(title+"$"+url)
		return videos
	#【标题清爽化】去掉书名号《》，保留 (年份)/(季数) 等尾巴
	def _strip_title_marks(self, title):
		try:
			import re as _re
		except Exception:
			return title
		if not title:
			return title
		t = str(title).strip()
		t = t.replace('《', '').replace('》', '')
		t = _re.sub(r'^\s+|\s+$', '', t)
		return t or title
	#【标题清爽化】去掉剧名前缀：从"第N集"或8位日期处截取到结尾, 保留区分信息
	def _clean_ep_title(self, title):
		try:
			import re as _re
		except Exception:
			return title
		if not title:
			return title
		t = str(title).strip()
		t = t.replace('《', '').replace('》', '')
		t = _re.sub(r'\s{2,}', ' ', t).strip()
		# 统一从"第N集"处截取到结尾(去掉前面重复剧名): 种墨园 第12集 -> 第12集; 布鲁伊3第1集卧室 -> 第1集卧室
		m = _re.search(r'第[0-9一二三四五六七八九十百千]+集', t)
		if m:
			return t[m.start():].strip()
		# 无"第N集": 从8位日期处截取到结尾(每日一期的电视栏目): 新闻联播20260916 21:00 -> 20260916 21:00
		m = _re.search(r'\d{8}', t)
		if m:
			return t[m.start():].strip()
		# 无集数无日期: 提取"N集"集数段兜底
		m = _re.search(r'[0-9一二三四五六七八九十百千]+\s*集', t)
		if m:
			return m.group(0).strip()
		return t or title
	#取剧集区
	def get_lineList(self,Txt,mark,after):
		circuit=[]
		origin=Txt.find(mark)
		while origin>8:
			end=Txt.find(after,origin)
			circuit.append(Txt[origin:end])
			origin=Txt.find(mark,end)
		return circuit	
	#正则取文本,返回数组	
	def get_RegexGetTextLine(self,Text,RegexText,Index):
		returnTxt=[]
		pattern = re.compile(RegexText, re.M|re.S)
		ListRe=pattern.findall(Text)
		if len(ListRe)<1:
			return returnTxt
		for value in ListRe:
			returnTxt.append(value)	
		return returnTxt
	#删除html标签
	def removeHtml(self,txt):
		soup = re.compile(r'<[^>]+>',re.S)
		txt =soup.sub('', txt)
		return txt.replace("&nbsp;"," ")
	#搜索
	def get_list_search(self,html,tid):
		jRoot = json.loads(html)
		jsonList=jRoot['list']
		videos=[]
		for vod in jsonList:
			url = vod['urllink']
			title =self.removeHtml(txt=vod['title'])
			# 列表标题清爽化: 去掉《》书名号
			title = self._strip_title_marks(title)
			img=vod['imglink']
			id=vod['id']
			brief=vod['channel']
			year=vod['uploadtime']
			if len(url) == 0:
				continue
			guid="{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,img,id,year,'',brief)
			videos.append({
				"vod_id":guid,
				"vod_name":title,
				"vod_pic":img,
				"vod_remarks":year
			})
		return videos
		return videos
	def get_list1(self,html,tid):
		jRoot = json.loads(html)
		videos = []
		data=jRoot['response']
		if data is None:
			return []
		jsonList=data['docs']
		for vod in jsonList:
			id = vod['lastVIDE']['videoSharedCode']
			title =vod['column_name']
			# 电视栏目分类标题清爽化: 去掉《》书名号
			title = self._strip_title_marks(title)
			url=vod['column_website']
			img=vod['column_logo']
			year=vod['column_playdate']
			brief=vod['column_brief']
			actors=''
			if len(url) == 0:
				continue
			guid="{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,img,id,year,actors,brief)
			#print(vod_id)
			videos.append({
				"vod_id":guid,
				"vod_name":title,
				"vod_pic":img,
				"vod_remarks":''
			})
		#print(videos)
		return videos
	#分类取结果
	def get_list(self,html,tid):
		jRoot = json.loads(html)
		videos = []
		data=jRoot['data']
		if data is None:
			return []
		jsonList=data['list']
		for vod in jsonList:
			url = vod['url']
			title =vod['title']
			# 分类列表标题清爽化: 去掉《》书名号
			title = self._strip_title_marks(title)
			# 再剥离tid分类前缀(如"电视剧奇迹"->"奇迹"), 使列表页标题清爽且与详情一致
			if tid and title and title.startswith(tid) and title != tid:
				_rest = title[len(tid):].strip()
				if _rest:
					title = _rest
			img=vod['image']
			id=vod['id']
			try:
				brief=vod['brief']
			except:
				brief=''
			try:
				year=vod['year']
			except:
				year=''
			try:
				actors=vod['actors']
			except:
				actors=''
			if len(url) == 0:
				continue
			guid="{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,img,id,year,actors,brief)
			#print(vod_id)
			videos.append({
				"vod_id":guid,
				"vod_name":title,
				"vod_pic":img,
				"vod_remarks":''
			})
		return videos
	# ============ 央视频 MP4 取流模块(纯Python AES-128-CBC, 无第三方依赖) ============
	_SBOX = [
		0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
		0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
		0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
		0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
		0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
		0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
		0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
		0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
		0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
		0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
		0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
		0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
		0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
		0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
		0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
		0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
	]
	_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]
	def _gf_mul(self, a, b):
		r = 0
		for _ in range(8):
			if b & 1: r ^= a
			hi = a & 0x80
			a = (a << 1) & 0xff
			if hi: a ^= 0x1b
			b >>= 1
		return r
	def _expand_key(self, key):
		w = [[key[4*i+j] for j in range(4)] for i in range(4)]
		for i in range(4, 44):
			t = list(w[i-1])
			if i % 4 == 0:
				t = t[1:] + t[:1]
				t = [self._SBOX[b] for b in t]
				t[0] ^= self._RCON[i//4 - 1]
			w.append([w[i-4][j] ^ t[j] for j in range(4)])
		return w
	def _aes_encrypt_block(self, block, w):
		state = [[block[r + 4*c] for c in range(4)] for r in range(4)]
		def add(rnd):
			for c in range(4):
				for r in range(4):
					state[r][c] ^= w[4*rnd + c][r]
		add(0)
		for rnd in range(1, 10):
			for r in range(4):
				for c in range(4):
					state[r][c] = self._SBOX[state[r][c]]
			for r in range(1, 4):
				state[r] = state[r][r:] + state[r][:r]
			for c in range(4):
				s0, s1, s2, s3 = state[0][c], state[1][c], state[2][c], state[3][c]
				state[0][c] = self._gf_mul(2, s0) ^ self._gf_mul(3, s1) ^ s2 ^ s3
				state[1][c] = s0 ^ self._gf_mul(2, s1) ^ self._gf_mul(3, s2) ^ s3
				state[2][c] = s0 ^ s1 ^ self._gf_mul(2, s2) ^ self._gf_mul(3, s3)
				state[3][c] = self._gf_mul(3, s0) ^ s1 ^ s2 ^ self._gf_mul(2, s3)
			add(rnd)
		for r in range(4):
			for c in range(4):
				state[r][c] = self._SBOX[state[r][c]]
		for r in range(1, 4):
			state[r] = state[r][r:] + state[r][:r]
		add(10)
		return bytes(state[r][c] for c in range(4) for r in range(4))
	def _aes_cbc_encrypt(self, key, iv, plain):
		w = self._expand_key(key)
		padlen = 16 - (len(plain) % 16)
		plain = plain + bytes([padlen]) * padlen
		out = b""
		prev = iv
		for i in range(0, len(plain), 16):
			blk = bytes(plain[i + j] ^ prev[j] for j in range(16))
			enc = self._aes_encrypt_block(blk, w)
			out += enc
			prev = enc
		return out
	# ============ 央视频 cKey(纯Python AES-128-CBC) ============
	def _ysp_ckey(self, vid, ts, guid, sdtfrom='4330701'):
		Tt = '4E2918885FD98109869D14E0231A0BF4'
		At = '16B17E519DDD0CE5B79D7A63A4DD801C'
		sr = 'mg3c3b04ba'; appVer = '1.2.3'
		Un = 'https://www.yangshipin.c'
		Mn = 'node.js/24'
		zn = 'https://www.baidu.com/'
		Hn = 'undefined'; Bn = 'undefined'; Gn = 'Linux arm64'
		Fn = ('|' + vid + '|' + str(ts) + '|' + sr + '|' + appVer + '|' + guid + '|' + str(sdtfrom)
			+ '|' + Un + '|' + Mn + '|' + zn + '|' + Hn + '|' + Bn + '|' + Gn + '|')
		Yn = 0
		for ch in Fn:
			Yn = (Yn << 5) - Yn + ord(ch) & 0xFFFFFFFF
		Xn = '|' + str(Yn) + Fn
		key = bytes.fromhex(Tt)
		iv = bytes.fromhex(At)
		ct = self._aes_cbc_encrypt(key, iv, Xn.encode('utf-8'))
		return '--01' + ct.hex().upper()
	# ============ 央视频点播 MP4 直链(vid -> /playvinfo -> 服务端定档, 原样播) ============
	def get_ysp_mp4(self, vid):
		"""vid -> /playvinfo -> 一条可播 MP4 直链。★照搬官网「自动选择分辨率」。

		官网两张截图把规则说死了:
		  · 新闻联播: 蓝光1080P 免费        -> 自动播 1080P
		  · 走遍中国: 蓝光1080P 标「会员」  -> 自动播 超清720P
		请求里的 defn=fhd 只是【能力声明】(官网 HAR 的 body 逐字同款), 不是点名要 1080:
		服务端按片源/会员态下发「最高可用免费档」, 播放器原样播放 ——
		不点名 720、不强求 1080、不挑档、不重试、不反证分辨率。

		HAR 硬证据: get_video_info body 逐字 "defn":"fhd"; 响应 vl.vi 唯一元素就是
		服务端下发的那一档; watch_record 上报 iHD=fhd。

		★前十几轮「一会儿720一会儿1080」的根因: 代码拿 vh/gdvz10004/fl.fi 去判断
		  「这是不是 1080」, 认不出就把整条流丢掉, 再换域名重试 / 掉进 shd 骨架 ——
		  服务端对会员节目自动降级的 720P 本该直接播, 却被我扔了。本版全部删除。

		仅两种例外(保证不黑屏, 与清晰度选择无关):
		  ① 网络异常 -> 换下一个域名;
		  ② 服务端明确拒发 fhd(exem 非 0/2, 真会员/无此档) -> 按原文件 shd/sd 降级。
		其余一律: 拿到 vl.vi 第一条带 fvkey 的流, 拼好直链立即返回。"""
		import ssl, urllib.request, time, json
		sdtfrom = '4330701'
		_UA_BASE = ('Mozilla/5.0 (iPhone; CPU iPhone OS %s like Mac OS X) '
			"AppleWebKit/605.1.15 (KHTML, like Gecko) Version/%s Mobile/15E148 Safari/604.1")
		FULL_HDRS = {
			'User-Agent': _UA_BASE % ('16_0','16.0'), 'Referer': 'https://v.yangshipin.cn/',
			'yspappid': '539073109', 'platform': '109', 'app-platform': 'm',
			'app-version': '1.0.0', 'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
			'Connection': 'keep-alive',
		}
		ctx = ssl._create_unverified_context()
		_YSF_DOMAINS = ['playvv.yangshipin.cn','playvv.ysp.cctv.cn',
				'bkplayvv.ysp.cctv.cn','playvv6.ysp.cctv.cn']

		def _request(defn, domain):
			'''返回 ('OK', 直链) / 'NETERR' / 'REJECT' / 'EMPTY'。'''
			guid = _YSP_DEVICE_GUID
			ts = int(time.time())
			ck = self._ysp_ckey(vid, ts, guid, sdtfrom)
			if len(ck) < 20:
				time.sleep(0.3); return ('NETERR', '')
			params = {
				'guid':guid,'platform':sdtfrom,'vid':vid,'defn':defn,'charge':'0','defaultfmt':'auto',
				'otype':'json','defnpayver':'1','appVer':'1.2.3','sphttps':'1','sphls':'1','spwm':'4',
				'defsrc':'2','encryptVer':'8.1','sdtfrom':sdtfrom,'cKey':ck
				# 不传 dtype / channel / adjust 才能拿到 MP4 直链(原文件口径, 已验证可播)
			}
			url = 'https://' + domain + '/playvinfo?' + urllib.parse.urlencode(params)
			try:
				raw = urllib.request.urlopen(urllib.request.Request(url, headers=FULL_HDRS),
							timeout=8, context=ctx).read().decode('utf-8', errors='replace')
			except Exception:
				return ('NETERR', '')
			t = raw.strip()
			if t.startswith('('): t = t[1:]
			if t.endswith(')'): t = t[:-1]
			t = t.strip().rstrip(';').strip()
			try:
				jo = json.loads(t)
			except Exception:
				return ('NETERR', '')
			payload, ep, fl_map = _ysp_play_payload(jo)
			if payload.get('exem', -1) not in (0, 2):
				return ('REJECT', '')
			vi_list = (payload.get("vl") or {}).get("vi") or []
			if not isinstance(vi_list, list): vi_list = []
			for vi in vi_list:
				if not isinstance(vi, dict): continue
				try:
					fn = vi['fn']; fvkey = vi['fvkey']
					base = vi['ul']['ui'][0]['url'].rstrip('/') + '/'
				except Exception:
					continue
				if not fvkey: continue
				_vh = vi.get('vh') or 0
				if _vh and _vh < 720: continue    # 720P 硬底线: 仅服务端明确给 <720 时跳过
				# ★只取服务端下发的第一条流, 不看 vh / 不比档 / 不换域名凑 1080
				_ysp_diag('playvinfo', 'defn=%s 服务端下发档 vh=%s fn=%s -> 原样播放'
					% (defn, vi.get('vh'), (fn or '')[:32]))
				if ep:
					cand = (base + fn).rstrip('/') + '?vkey=' + fvkey
					cand += ep if ep.startswith(('&','?')) else ('&' + ep)
				else:
					cand = base + fn + '?vkey=' + fvkey + '&sdtfrom=' + sdtfrom + '&guid=' + guid
				return ('OK', cand)
			return ('EMPTY', '')

		# ===== 主路径: 一条 defn=fhd, 服务端给什么档就播什么档 =====
		for _d in _YSF_DOMAINS:
			_st, _u = _request('fhd', _d)
			if _st == 'OK':
				return _u
			if _st == 'NETERR':
				continue          # 仅网络异常换域名
			break                # REJECT / EMPTY: 交给下面保底降级

		# ===== 保底: fhd 明确不可用时, 原文件骨架 shd -> sd =====
		for defn in ('shd', 'sd'):
			for _d in _YSF_DOMAINS:
				_st, _u = _request(defn, _d)
				if _st == 'OK':
					return _u
		return ''


	# ============ 选集VIP轻量判定(单次playvinfo, exem判据, 约0.7s) ============
	def _ysp_is_vip(self, vid, timeout=5):
		# 仅对央视频vid(形如 z0000459kta / r000095lofp)判定
		# ★判据修正(经免费《布鲁伊》与真VIP《人民的选择》完整请求头逐档对照实测确认):
		#   服务端用【该档是否返回带完整fvkey的可播vl】表达能否完整免费播放:
		#   - 免费可播: 至少一个档位返回 exem∈{0,2} 且 vl.vi 含完整fvkey(>50位)与取流url
		#               → 判为免费(不标VIP); 如《布鲁伊》shd档 exem=2 em=null 带vh=720完整流
		#   - 真付费:   所有有效档位(exem∈{0,2})均无vl(em=100仅错误码)或拿不到完整流
		#               → 判为VIP; 如《人民的选择》各档 exem=2 em=100 无vl(get_ysp_mp4取流EMPTY)
		#   ⚠不要用"exem=2一刀切判VIP": exem=2对带可播vl的免费剧同样成立(em=null),
		#     这是此前"标VIP却能播放"误判的根因; 现判据与get_ysp_mp4取流能力严格一致
		# 档位轮询 shd->fhd->sd(见 _YSP_DEFN_VIP): 官网多数节目 fhd 是会员档,
		#   先探 shd 才能在"仅1080P收费/720P免费"时正确判为免费; 免费剧首档即定论。
		#   ⚠此处顺序刻意与取流链不同, 不能为了"消除重复"合并成 fhd 优先,
		#     否则遇 fhd 会员档就会在本函数第2个 return 处误判 VIP。
		import random, string, ssl, urllib.request, urllib.parse, time, json
		sdtfrom = '4330701'
		_DEFNS = _YSP_DEFN_VIP
		UAS = [
			"Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
			"Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
		]
		ctx = ssl._create_unverified_context()
		for attempt in range(2):
			for defn in _DEFNS:
				try:
					guid = _YSP_DEVICE_GUID
					ts = int(time.time())
					ck = self._ysp_ckey(vid, ts, guid, sdtfrom)
					if len(ck) < 20:
							time.sleep(0.3)
							continue
					params = {
						'guid':guid,'platform':sdtfrom,'vid':vid,'defn':defn,'charge':'0',
						'defaultfmt':'auto','otype':'json','defnpayver':'1','appVer':'1.2.3',
						'sphttps':'1','sphls':'1','spwm':'4','defsrc':'2','encryptVer':'8.1',
						'sdtfrom':sdtfrom,'cKey':ck
					}
					url = 'https://playvv.yangshipin.cn/playvinfo?' + urllib.parse.urlencode(params)
					hdr = {
						'User-Agent':UAS[attempt % len(UAS)],
						'Referer':'https://v.yangshipin.cn/','yspappid':'539073109','platform':'109',
						'app-platform':'m','app-version':'1.0.0','Accept':'*/*',
						'Accept-Language':'zh-CN,zh;q=0.9','Connection':'keep-alive'
					}
					raw = urllib.request.urlopen(urllib.request.Request(url,headers=hdr), timeout=timeout, context=ctx).read().decode('utf-8','replace')
					s = raw.strip()
					if s.startswith('('): s = s[1:]
					if s.endswith(')'): s = s[:-1]
					s = s.strip().rstrip(';').strip()
					jo = json.loads(s)
					exem = jo.get('exem')
					if exem not in (0, 2):
							# 无有效档(-12=该档不存在/em=85): 换下一档
							continue
					# 有效档(exem∈{0,2}): 关键看是否给出带完整fvkey的可播vl
					if jo.get('vl') and jo['vl'].get('vi'):
						vi = jo['vl']['vi'][0]
						fvkey = vi.get('fvkey') or ''
						if len(fvkey) > 50 and vi.get('ul'):
							# 带完整fvkey+取流url = 该档可完整免费播放 → 判免费(不标VIP)
							return False
					# 有效档但无完整流(仅em/errinfo, 或试看短fvkey): 属真付费/VIP
					return True
				except Exception:
					continue
			if attempt < 1 and defn == _DEFNS[-1]:
				time.sleep(0.6)
		# 全部档位轮询2轮仍无法判定(持续异常/全-12): 保守兜底判免费, 不误标VIP
		return False