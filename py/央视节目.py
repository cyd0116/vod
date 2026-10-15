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

# ===== 央视频"电视栏目/节目大全"48栏目静态清单 (lid, 栏目名, 栏目cid, 期次备注) =====
# 来源: 日志category(program_library)返回的完整栏目清单, 与别人"电视栏目"分类一致。
# vod_id三段式: library~~~<lid>~~~<cid>; detailContent用 lid 取全部期次(~~~cid)。
_YSP_COLUMNS = [
	("10492","新闻联播","skmna7n7ptliakk","2026/9/17期"),
	("10028","百家讲坛","rc2u01hhflli74n","2026/9/17期"),
	("10031","今日说法","sxcrcv4u3ulhveo","2026/9/17期"),
	("10151","焦点访谈","r8ap1hpwf7licpc","2026/9/17期"),
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

# ============ 央视频 program 分类接口 (纯py签名, host必须m站) ============
# 与央视频页面数据"完全一致"的分类数据源。签名公式已彻底逆向并三重验证。
import hashlib as _hl, random as _rd
_YSP_PROGRAM_URL = "https://csapi.yangshipin.cn/voapi/omsotm/media/v2/program"
_YSP_TOKEN_URL  = "https://h5access.yangshipin.cn/web/open/token"
_YSP_PGUID      = "mu1k3hl8_8zhsvo0vhwn"
_YSP_PCOOKIE    = ("guid=%s; versionName=99.99.99; versionCode=999999; vplatform=109; platformVersion=Chrome; deviceModel=108; newLogin=1; pc_version=1.1.16; _abfpc=951791353206c47aa9fc22c73c8c99618fd54a77_2.0; cna=16fbd097dc393531d33a81a1a558e99b" % _YSP_PGUID)
_YSP_PROG_CID   = {"动画片":"program_cid_775","电视剧":"program_cid_776","纪录片":"program_cid_774","特别节目":"program_cid_777","电影":"program_cid_778"}
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
_YSP_TOKEN_CACHE = {"tk":None, "ts":0}

def _ysp_extval(extend, key):
	"""从壳子 extend 提取指定筛选 key 的选中值(兼容 字符串 或 {n,v} dict)。"""
	if not isinstance(extend, dict):
		return ''
	v = extend.get(key, '')
	if isinstance(v, dict):
		return v.get('v') or v.get('n') or ''
	return v or ''

def _ysp_build_fv(pcid, tid, extend):
	"""壳子 extend(中文名) -> 央视频 program 接口 filterValue 数值串(与央视频完全一致)。
	各分类"类型"key名不同: 动画片=childhood_types / 电视剧=drama_types /
	纪录片=documentary_types / 特别节目=special_program_type / 电影=cctvfilm_type。
	通用: 地区=area_id, 年份=first_onlinetime。
	壳子key: datafl-sc=类型 / datadq-area=地区 / datanf-year=年份。
	值在央视频无对应枚举(如壳子独有"谍战/欧洲"等)时回退'全部'(-1),
	避免非法枚举导致接口报错; 年份/字母/频道筛选央视频不支持故忽略。"""
	fmap = _YSP_FILTER_MAP.get(pcid, {})
	_type_key = {'动画片':'childhood_types','电视剧':'drama_types','纪录片':'documentary_types',
	             '特别节目':'special_program_type','电影':'cctvfilm_type'}.get(tid, '')
	def _v(k, val, default='-1'):
		if not val:
			return default
		m = fmap.get(k, {})
		if val in m:
			return m[val]
		if str(val).isdigit():
			return str(val)
		return default
	parts = ['d11=%s' % pcid]
	tv = _ysp_extval(extend, 'datafl-sc')
	parts.append('%s=%s' % (_type_key, _v(_type_key, tv)) if _type_key else 'childhood_types=-1')
	parts.append('first_onlinetime=%s' % _v('first_onlinetime', _ysp_extval(extend, 'datanf-year')))
	parts.append('area_id=%s' % _v('area_id', _ysp_extval(extend, 'datadq-area')))
	parts.append('sort=6')
	return '&'.join(parts)

def _ysp_prs(n):
	return ''.join(_rd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))

def _ysp_get_token():
	"""实时获取签名 token(5分钟时效), 带240s内存缓存。失败返回None。"""
	now = time.time()
	if _YSP_TOKEN_CACHE["tk"] and now - _YSP_TOKEN_CACHE["ts"] < 240:
		return _YSP_TOKEN_CACHE["tk"]
	import ssl
	ts  = str(int(time.time()*1000)); rnd = _ysp_prs(16)
	url = "%s?yspappid=539073109&guid=%s&vappid=59306155&vsecret=b42702bf7309a179d102f3d51b1add2fda0bc7ada64cb801&raw=1&version=v1&ts=%s&rnd=%s" % (_YSP_TOKEN_URL, _YSP_PGUID, ts, rnd)
	hdr = {"User-Agent":"Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.120 Mobile Safari/537.36",
	       "Referer":"https://m.yangshipin.cn/static/m/pool","Origin":"https://m.yangshipin.cn",
	       "Accept":"application/json, text/plain, */*","Cookie":_YSP_PCOOKIE}
	ctx = ssl._create_unverified_context()
	try:
		d  = urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20, context=ctx).read().decode('utf-8','replace')
		tk = json.loads(d).get('data',{}).get('token')
	except Exception:
		tk = None
	if tk:
		_YSP_TOKEN_CACHE["tk"] = tk; _YSP_TOKEN_CACHE["ts"] = now
	return tk

def _ysp_program(filterValue, page=1, size=50):
	"""央视频 program 分类接口 -> [(title, cid, cover, vidNum, updateNum), ...] 或 []。
	签名：yspsdkinput=hex_md5(按key排序拼接body)；yspsdksign=md5("{guid};m.yangshipin.cn;{token};https:;539073109;{input};")+"-"+input。
	host 必须 m.yangshipin.cn(www返回服务异常)。"""
	import ssl
	token = _ysp_get_token()
	if not token: return []
	body = {"filterValue":filterValue, "page":page, "pageSizeT":size}
	pairs = ["%s=%s" % (k, urllib.parse.unquote(str(body[k]))) for k in sorted(body.keys())]
	ysp  = _hl.md5("&".join(pairs).encode()).hexdigest()
	seq  = str(page); reqid = "999999" + _ysp_prs(10) + str(int(time.time()*1000))
	input_str = "%s-%s-%s-%s" % (ysp, _YSP_PGUID, seq, reqid)
	raw  = "%s;m.yangshipin.cn;%s;https:;539073109;%s;" % (_YSP_PGUID, token, input_str)
	sign = _hl.md5(raw.encode()).hexdigest() + "-" + input_str
	hdr = {"Accept":"application/json, text/plain, */*","Content-Type":"application/json",
	       "yspappid":"539073109","platform":"109","app-platform":"pc","app-version":"1.0.0",
	       "yspsdkinput":ysp,"yspsdksign":sign,"seqId":seq,"request-id":reqid,
	       "User-Agent":"Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.120 Mobile Safari/537.36",
	       "Referer":"https://m.yangshipin.cn/static/m/pool","Origin":"https://m.yangshipin.cn","Cookie":_YSP_PCOOKIE}
	ctx = ssl._create_unverified_context()
	try:
		r = urllib.request.urlopen(urllib.request.Request(_YSP_PROGRAM_URL, data=json.dumps(body).encode(), headers=hdr, method='POST'), timeout=20, context=ctx)
		rawb = r.read()
	except Exception:
		return []
	fields = _YspPB(rawb).read()
	data_f = [v for f,_,v in fields if f==2]
	if not data_f: return []
	data_fields = _YspPB(data_f[0]).read()
	progs = [v for f,_,v in data_fields if f==3]
	out = []
	for p in progs:
		d = {}
		for fn,wt,v in _YspPB(p).read():
			if wt==2 and isinstance(v, bytes):
				s = _ysp_s(v)
				if s: d.setdefault(fn, []).append(s)
			elif wt==0: d.setdefault(fn, []).append(v)
		title = d.get(5,[''])[0]; cid = d.get(4,[''])[0]; cover = d.get(8,[''])[0]
		vidnum = d.get(11,['']); upd = d.get(12,[''])
		if cid and title:
			out.append((title, cid, cover, (vidnum[0] if vidnum else ''), (upd[0] if upd else '')))
	return out

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
	播放走 get_ysp_mp4 取720P MP4直链。"""
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
		print("============{0}============".format(extend))
		pass
	def destroy(self):
		pass
	def isVideoFormat(self,url):
		pass
	def manualVideoCheck(self):
		pass
	def homeContent(self,filter):
		result = {}
		cateManual = {
			"栏目大全":"节目大全",
			"电视剧": "电视剧",
			"动画片": "动画片",
			"纪录片": "纪录片",
			"特别节目": "特别节目",
			"电影": "电影"
		}
		classes = []
		for k in cateManual:
			classes.append({
				'type_name':k,
				'type_id':cateManual[k]
			})
		result['class'] = classes
		if(filter):
			result['filters'] = self.config['filter']
		return result
	def homeVideoContent(self):
		result = {
			'list':[]
		}
		return result
	def categoryContent(self,tid,pg,filter,extend):
		# 【健壮性】extend 可能被壳子以字符串传入(非dict), 统一转成dict避免 .keys() 崩溃
		if not isinstance(extend, dict):
			try:
				extend = json.loads(extend) if isinstance(extend, str) and extend else {}
			except Exception:
				extend = {}
		result = {}
		month = ""#月
		year = ""#年
		area=''#地区
		channel=''#频道
		datafl=''#类型
		letter=''#字母
		pagecount=24
		if tid in ('动画片','电视剧','纪录片','特别节目','电影'):
			# 【央视频节目库·完全一致】program 接口(纯py签名, host=m.yangshipin.cn),
			#   数据与央视频页面完全一致。vod_id 四段式: prog~~~<cid>~~~<title>~~~<cover>,
			#   detailContent 识别 prog~~~ 前缀, 用 cid 打开详情页取全集真实vid。
			_pcid = _YSP_PROG_CID.get(tid, '')
			# filterValue 由 extend(壳子中文名) 映射为央视频数值枚举(与央视频完全一致)。
			#   类型(datafl-sc)/地区(datadq-area)/年份(datanf-year) 均按分类映射到对应key;
			#   壳子独有枚举(如谍战/欧洲等)央视频无对应 -> 回退全部(-1)。
			_fv = _ysp_build_fv(_pcid, tid, extend)
			_pg = int(pg) if str(pg).isdigit() else 1
			_progs = _ysp_program(_fv, page=_pg, size=50)
			videos=[]
			for _title,_cid,_cover,_vn,_upd in _progs:
				_rem = ('%s集' % _upd) if _upd else ''
				videos.append({
					"vod_id": "prog~~~%s~~~%s~~~%s" % (_cid, _title, _cover),
					"vod_name": self._strip_title_marks(_title),
					"vod_pic": _cover,
					"vod_remarks": _rem
				})
			pagecount=50
		elif tid=='节目大全':
			# 【电视栏目·完整复刻别人机制】直接返回48栏目静态清单(内置 _YSP_COLUMNS,
			#   与别人"电视栏目"分类一致), 不再请求老接口 api.cntv.cn/lanmu/columnSearch。
			#   vod_id三段式: library~~~<lid>~~~<cid>, detailContent用 lid 取全部期次。
			# ★图片修复: 原 vod_pic 用旧模板 columnPic/<lid>/20210129/default.jpg 已全部404(全无图)。
			#     改为从每个栏目 lid 详情页 __STATE_video__.payloads.sharevideo.pastCover.coverList[0]
			#     提取真实封面图(poster.poster.imageUrl, 实测200可访问)。单栏目超时/失败则留空占位,
			#     避免列表加载卡顿; 仅首页(pg==1)提取, 翻页沿用。
			#     ★性能优化: 48栏目改为 ThreadPoolExecutor 并行提取(每栏目一个线程), 串行约29.6s
			#     降至约2.3s; 并用 _YSP_COV_CACHE 内存缓存, 同一会话内重复进入不再重复请求。
			videos=[]
			_cov = {}
			if pg == '1' or pg == 1:
				if not getattr(self, '_ysp_cov_cache', None):
					self._ysp_cov_cache = {}
				_missing = [_c for _c in _YSP_COLUMNS if _c[0] not in self._ysp_cov_cache]
				if _missing:
					from concurrent.futures import ThreadPoolExecutor
					def _cov_fetch(_row):
						_lid = _row[0]
						try:
							_js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&lid=%s' % _lid)
							_cl = ((((_js or {}).get('payloads',{}) or {}).get('sharevideo',{}) or {}).get('pastCover',{}) or {}).get('coverList',[]) or []
							if _cl:
								return (_lid, (((_cl[0].get('poster',{}) or {}).get('poster',{}) or {}).get('imageUrl') or '').split('/1080?')[0])
						except Exception:
							pass
						return (_lid, '')
					with ThreadPoolExecutor(max_workers=10) as _ex:
						for _lid,_img in _ex.map(_cov_fetch, _missing):
							self._ysp_cov_cache[_lid] = _img
				_cov = dict(self._ysp_cov_cache)
			for _lid,_name,_cid,_rem in _YSP_COLUMNS:
				_vod_id = 'library~~~%s~~~%s' % (_lid, _cid)
				videos.append({
					"vod_id": _vod_id,
					"vod_name": self._strip_title_marks(_name),
					"vod_pic": _cov.get(_lid,''),
					"vod_remarks": _rem
				})
			pagecount=20
		else:
			url = 'https://tv.cctv.com/epg/index.shtml'

		if tid in ('节目大全','','动画片','电视剧','纪录片','特别节目','电影'):
			# 已在上方用静态清单/program接口填充videos, 直接跳过网络请求(url未赋值, 不能调webReadFile)
			pass
		else:
			htmlText =self.webReadFile(urlStr=url,header=self.header)
			videos =self.get_list(html=htmlText,tid=tid)
		#print(videos)
		
		result['list'] = videos
		result['page'] = pg
		# 分页: pagecount 表示"每页条数上限"。当本页已满(=本页条数达到上限)时,
		#   旧逻辑返回9999暗示"还有下一页", 这适合无限滚动的节目库分类;
		#   但对固定有限列表(pagecount=1)会误导壳子一直翻页导致重复。
		#   ★修复: 仅当 pagecount>1 时才按"本页满→可能有下一页"返回9999;
		#     pagecount<=1 的固定单页列表返回实际页数, 让壳子知道到底, 不再翻页。
		result['pagecount'] = (9999 if len(videos)>=pagecount else pg) if pagecount>1 else pg
		result['limit'] = 90
		result['total'] = 999999
		return result
	def detailContent(self,array):
		result={}
		# 【电视栏目·修复】壳子把 categoryContent 返回的三段式 vod_id(library~~~<lid>~~~<cid>)
		#   原样作为 ids[0] 传入, 不会用 ### 或任何分隔符预拆。此处优先识别 library~~~ 三段式:
		#   从 _YSP_COLUMNS_MAP 反查栏目名, 设置 tid='节目大全' 走对应分支, 避免 aid[3] 越界崩溃。
		_raw0 = array[0]
		if isinstance(_raw0, str) and _raw0.startswith('library~~~'):
			_parts = _raw0.split('~~~')
			_lid = _parts[1] if len(_parts) > 1 else ''
			_cid = _parts[2] if len(_parts) > 2 else ''
			_row = _YSP_COLUMNS_MAP.get(_lid)
			tid = '节目大全'
			title = self._strip_title_marks(_row[0]) if _row else ''
			logo = (self._ysp_cov_cache or {}).get(_lid, '') if hasattr(self, '_ysp_cov_cache') else ''
			id = 'library~~~%s~~~%s' % (_lid, _cid)
			vod_year = ''
			actors = ''
			brief = _row[2] if _row else ''
			lastVideo = ''
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
		if tid=="节目大全":
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
				# 【program分类·取全集】以节目cid打开详情页取 shareLongVideoRec.episodes.videoList
				#   全集真实vid, 产"第N集$vid"播放串(fromId2='央视频' -> playerContent直接取MP4直链)。
				#   比 _ysp_best_album(剧名搜索)更精确: 规避同名剧歧义, 与央视频页面数据完全一致。
				videoList=[]
				fromId2='央视频'
				_seen=set()
				try:
					_js=_ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s'%id)
					if _js:
						_sv=(_js.get('payloads',{}) or {}).get('sharevideo',{}) or {}
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
					videoList=[]
				# 兜底: 详情页取不到全集 -> 用剧名搜索最佳全集专辑(完整复刻影视剧类分支逻辑)
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
				# 【二次兜底·单集特别节目】详情页无 episodes 且搜索无全集专辑时
				#   (如"2026开学第一课"是 is_complete 单集, shareLongVideoRec 仅含
				#   watchingfocus 无 episodes), 回退用 sharevideo 顶层 vid(单集)生成
				#   播放串, 否则壳子详情页进不去/无法播放。
				if not videoList:
					_sv2 = locals().get('_sv', {}) or {}
					_top_vid = _sv2.get('vid','')
					if _top_vid and _top_vid not in _seen:
						_tt2 = str(_sv2.get('title') or '').strip() or title
						_seen.add(_top_vid)
						videoList.append('%s$%s'%(_tt2,_top_vid))
			elif tid=="搜索":
				# 【问题④修复】搜索的央视网页短视频(如"秘境之眼")仅提供HLS线路, 壳子EXO对其
				#   AAC-LC(48000Hz)音频轨AudioTrack直通初始化失败(AUDIO_TRACK_INIT_FAILED)导致
				#   播放中断/不足2分钟。这里抓取网页提取32位hex guid作为播放id, 让playerContent
				#   命中32位hex guid分支: _ysp_guid_to_vid映射央视频vid -> get_ysp_mp4取720P MP4直链,
				#   彻底绕开HLS音频直通bug, 同时满足720P+可拖进度条。
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
				if tid=="节目大全":
					# 【电视栏目·完整复刻别人机制】解析三段式 library~~~<lid>~~~<cid> 取 lid,
					#   调 video?type=0&lid= 取 pastCover.coverList(25期含最新) -> 产"期次标题$~~~<cid>"。
					#   与别人detailContent返回完全一致: 播放串id=~~~<cid>, playerContent剥离~~~后
					#   取详情页真实vid -> get_ysp_mp4 取720P MP4直链(实测0.4s成功)。
					videoList=[]
					fromId2='央视频'
					_seen=set()
					_lid=None
					_mm=re.match(r'library~~~(\d+)~~~', str(id)) or re.match(r'^(\d+)$', str(id))
					if _mm: _lid=_mm.group(1)
					if _lid and _lid in _YSP_COLUMNS_MAP:
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
					# (lazy保留guid, 点播时playerContent按32位hex guid映射取720P MP4直链)
					videoList=self.get_EpisodesList(jsonList=jsonList, map_to_vid=True, lazy=True)
					if len(videoList)<1:
						htmlTxt=self.webReadFile(urlStr=lastVideo,header=self.header)
						if tid=="电视剧" or tid=="纪录片":
							patternTxt=r"'title':\s*'(?P<title>.+?)',\n{0,1}\s*'brief':\s*'(.+?)',\n{0,1}\s*'img':\s*'(.+?)',\n{0,1}\s*'url':\s*'(?P<url>.+?)'"
						elif tid=="特别节目":
							patternTxt=r'class="tp1"><a\s*href="(?P<url>https://.+?)"\s*target="_blank"\s*title="(?P<title>.+?)"></a></div>'
						elif tid=="动画片":
							patternTxt=r"'title':\s*'(?P<title>.+?)',\n{0,1}\s*'img':\s*'(.+?)',\n{0,1}\s*'brief':\s*'(.+?)',\n{0,1}\s*'url':\s*'(?P<url>.+?)'"
						elif tid=="节目大全":
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
		#   纪录片/特别节目/电影/节目大全"分类完全同源、数据完全一致。返回 prog~~~<cid>~~~<title>
		#   四段式 vod_id —— detailContent 的 prog 专用分支用 cid 打开央视频详情页取全集真实vid,
		#   playerContent 直接 get_ysp_mp4 取720P MP4直链。至此壳子搜索与分类数据源完全统一。
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
		#   精确映射为央视频vid -> get_ysp_mp4取720P MP4直链; 映射失败留空(绝不嗅探/不设parse=1)。
		#   节目大全/电视剧/动画片/纪录片/特别节目分类的选集guid均为32位hex,统一由此接管。
		# 【按App重写】"央视频"播放源: 播放串里的id已是真实vid(如 x0000400dt9),
		#   直接get_ysp_mp4取720P MP4直链(vid为核心, 不再依赖guid映射)。
		if flag=='央视频':
			try:
				_iphone = {
					'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
					'Referer':'https://v.yangshipin.cn/'
				}
				# 【按App重写·电视栏目期次适配】播放串里的id可能为"~~~<cid>"格式
				#   (别人"电视栏目"分类的期次id, 如 ~~~skmna7n7ptliakk)。
				#   cid不是真实vid, 需先剥离"~~~"前缀, 打开 video?type=0&cid= 详情页
				#   取 sharevideo.vid 真实vid, 再 get_ysp_mp4 取720P MP4直链。
				_play_id = id
				if isinstance(_play_id, str) and _play_id.startswith('~~~'):
					_cid = _play_id[3:]
					_real = None
					try:
						_js = _ysp_fetch_state('https://m.yangshipin.cn/video?type=0&cid=%s' % _cid)
						if _js:
							_real = ((_js.get('payloads',{}) or {}).get('sharevideo',{}) or {}).get('vid','')
					except Exception:
						_real = None
					if _real:
						_play_id = _real
				# 用 _play_id 取 720P MP4 直链（_play_id 此时是真实 vid）
				try:
					cand = self.get_ysp_mp4(vid=_play_id)
				except Exception:
					cand = None
				if cand and cand.startswith('http'):
					headers = _iphone
					url = cand
					result["format"] = 'video/mp4'
			except Exception:
				pass
			if not url:
				# vid取流失败 -> 通常为央视频VIP付费内容(免费剧瞬时成功, VIP剧拒发流)
				#   给VIP标识提示, 而非静默黑屏
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
	"filter": {
	"电视剧":[{"key":"datafl-sc","name":"类型","value":[{"n":"历史","v":"历史"},{"n":"军事","v":"军事"},{"n":"武侠","v":"武侠"},{"n":"偶像","v":"偶像"},{"n":"爱情","v":"爱情"},{"n":"刑侦","v":"刑侦"},{"n":"古装","v":"古装"},{"n":"喜剧","v":"喜剧"},{"n":"奇幻","v":"奇幻"},{"n":"家庭","v":"家庭"},{"n":"悬疑","v":"悬疑"},{"n":"战争","v":"战争"},{"n":"剧情","v":"剧情"},{"n":"青春","v":"青春"},{"n":"神话","v":"神话"},{"n":"都市","v":"都市"},{"n":"农村","v":"农村"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"中国香港","v":"中国香港"},{"n":"中国台湾","v":"中国台湾"},{"n":"美国","v":"美国"},{"n":"英国","v":"英国"},{"n":"泰国","v":"泰国"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"动画片":[{"key":"datafl-sc","name":"类型","value":[{"n":"益智","v":"益智"},{"n":"冒险","v":"冒险"},{"n":"合家欢","v":"合家欢"},{"n":"竞技","v":"竞技"},{"n":"少年","v":"少年"},{"n":"真人","v":"真人"},{"n":"魔幻科幻","v":"魔幻科幻"},{"n":"战斗","v":"战斗"},{"n":"儿童故事","v":"儿童故事"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"日本","v":"日本"},{"n":"英国","v":"英国"},{"n":"欧美","v":"欧美"}]}],
	"纪录片":[{"key":"datafl-sc","name":"类型","value":[{"n":"文史","v":"文史"},{"n":"自然","v":"自然"},{"n":"美食","v":"美食"},{"n":"军事","v":"军事"},{"n":"科技","v":"科技"},{"n":"体育","v":"体育"},{"n":"健康","v":"健康"},{"n":"农业","v":"农业"},{"n":"旅游","v":"旅游"},{"n":"社会","v":"社会"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"日本","v":"日本"},{"n":"韩国","v":"韩国"},{"n":"英国","v":"英国"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"特别节目":[{"key":"datafl-sc","name":"类型","value":[{"n":"综艺","v":"综艺"},{"n":"资讯","v":"资讯"},{"n":"文史","v":"文史"},{"n":"教育","v":"教育"},{"n":"体育","v":"体育"},{"n":"社会","v":"社会"},{"n":"法治","v":"法治"},{"n":"自然","v":"自然"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"其他","v":"其他"}]}],
	"电影":[{"key":"datafl-sc","name":"类型","value":[{"n":"传记","v":"传记"},{"n":"伦理","v":"伦理"},{"n":"冒险","v":"冒险"},{"n":"武侠","v":"武侠"},{"n":"动作","v":"动作"},{"n":"爱情","v":"爱情"},{"n":"历史","v":"历史"},{"n":"喜剧","v":"喜剧"},{"n":"奇幻","v":"奇幻"},{"n":"战争","v":"战争"},{"n":"恐怖","v":"恐怖"},{"n":"悬疑","v":"悬疑"},{"n":"科幻","v":"科幻"},{"n":"犯罪","v":"犯罪"},{"n":"动画","v":"动画"},{"n":"励志","v":"励志"},{"n":"剧情","v":"剧情"},{"n":"更多","v":"更多"}]}, {"key":"datadq-area","name":"地区","value":[{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"中国香港","v":"中国香港"},{"n":"日本","v":"日本"},{"n":"英国","v":"英国"},{"n":"泰国","v":"泰国"},{"n":"印度","v":"印度"}]}, {"key":"datanf-year","name":"年份","value":[{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"更早","v":"更早"}]}],
	"节目大全":[{"key":"cid","name":"频道","value":[{"n":"全部","v":""},{"n":"CCTV-1综合","v":"EPGC1386744804340101"},{"n":"CCTV-2财经","v":"EPGC1386744804340102"},{"n":"CCTV-3综艺","v":"EPGC1386744804340103"},{"n":"CCTV-4中文国际","v":"EPGC1386744804340104"},{"n":"CCTV-5体育","v":"EPGC1386744804340107"},{"n":"CCTV-6电影","v":"EPGC1386744804340108"},{"n":"CCTV-7国防军事","v":"EPGC1386744804340109"},{"n":"CCTV-8电视剧","v":"EPGC1386744804340110"},{"n":"CCTV-9纪录","v":"EPGC1386744804340112"},{"n":"CCTV-10科教","v":"EPGC1386744804340113"},{"n":"CCTV-11戏曲","v":"EPGC1386744804340114"},{"n":"CCTV-12社会与法","v":"EPGC1386744804340115"},{"n":"CCTV-13新闻","v":"EPGC1386744804340116"},{"n":"CCTV-14少儿","v":"EPGC1386744804340117"},{"n":"CCTV-15音乐","v":"EPGC1386744804340118"},{"n":"CCTV-16奥林匹克","v":"EPGC1634630207058998"},{"n":"CCTV-17农业农村","v":"EPGC1563932742616872"},{"n":"CCTV-5+体育赛事","v":"EPGC1468294755566101"}]},{"key":"fc","name":"分类","value":[{"n":"全部","v":""},{"n":"新闻","v":"新闻"},{"n":"体育","v":"体育"},{"n":"综艺","v":"综艺"},{"n":"健康","v":"健康"},{"n":"生活","v":"生活"},{"n":"科教","v":"科教"},{"n":"经济","v":"经济"},{"n":"农业","v":"农业"},{"n":"法治","v":"法治"},{"n":"军事","v":"军事"},{"n":"少儿","v":"少儿"},{"n":"动画","v":"动画"},{"n":"纪实","v":"纪实"},{"n":"戏曲","v":"戏曲"},{"n":"音乐","v":"音乐"},{"n":"影视","v":"影视"}]},{"key":"fl","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"}]},{"key":"year","name":"年份","value":[{"n":"全部","v":""},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"2004","v":"2004"},{"n":"2003","v":"2003"},{"n":"2002","v":"2002"},{"n":"2001","v":"2001"},{"n":"2000","v":"2000"}]},{"key":"month","name":"月份","value":[{"n":"全部","v":""},{"n":"12","v":"12"},{"n":"11","v":"11"},{"n":"10","v":"10"},{"n":"09","v":"09"},{"n":"08","v":"08"},{"n":"07","v":"07"},{"n":"06","v":"06"},{"n":"05","v":"05"},{"n":"04","v":"04"},{"n":"03","v":"03"},{"n":"02","v":"02"},{"n":"01","v":"01"}]}]
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
		# map_to_vid=True+lazy=True(节目大全): 保留原始guid在播放串, 由 playerContent
		#   在点播那一刻再为该集单独精确映射取vid(guid->日期->cid->vid->get_ysp_mp4 720P)。
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
			# 统一去剧名前缀: 从"第N集"或日期处截取到结尾(电视剧/动画片/栏目大全均适用)
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
		# 无"第N集": 从8位日期处截取到结尾(每日一期的栏目大全): 新闻联播20260916 21:00 -> 20260916 21:00
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
			# 栏目大全分类标题清爽化: 去掉《》书名号
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
	# ============ 央视频点播 MP4 直链(vid -> cKey -> /playvinfo -> 720P MP4直链) ============
	def get_ysp_mp4(self, vid, hdMode='hd'):
		import random, string, ssl, urllib.request, time, json
		sdtfrom = '4330701'
		# 档位failover: shd(720P超清)优先;但综艺/纪录片等按期次组织的视频服务端对"shd+auto"可能返回exem=-12(无档),
		#   而fhd/sd则直接给1280x720真档;hd仅864x486(480P)不满足720P硬约束,不入列表。
		_DEFNS = ['shd', 'fhd', 'sd']
		_UA_BASE = ("Mozilla/5.0 (iPhone; CPU iPhone OS %s like Mac OS X) "
			"AppleWebKit/605.1.15 (KHTML, like Gecko) Version/%s Mobile/15E148 Safari/604.1")
		_UA_VERS = [('16_0','16.0'),('16_6','16.6'),('15_5','15.5'),('17_0','17.0'),('17_4','17.4')]
		FULL_HDRS = {
			'User-Agent': _UA_BASE % _UA_VERS[0],
			'Referer': 'https://v.yangshipin.cn/',
			'yspappid': '539073109',
			'platform': '109',
			'app-platform': 'm',
			'app-version': '1.0.0',
			'Accept': '*/*',
			'Accept-Language': 'zh-CN,zh;q=0.9',
			'Connection': 'keep-alive',
		}
		ctx = ssl._create_unverified_context()
		# 多取流域名failover: H5主域名 -> APK官方域名 -> 备用域名 -> ipv6备用(实测最后一个常超时,仍保留兜底)
		_YSF_DOMAINS = ['playvv.yangshipin.cn','playvv.ysp.cctv.cn','bkplayvv.ysp.cctv.cn','playvv6.ysp.cctv.cn']
		for attempt in range(6):
			defn = _DEFNS[attempt % len(_DEFNS)]
			ua_ver = _UA_VERS[attempt % len(_UA_VERS)]
			FULL_HDRS['User-Agent'] = _UA_BASE % ua_ver
			guid = 'mu1ja7md_' + ''.join(random.choice(string.ascii_letters+string.digits) for _ in range(18))
			ts = int(time.time())
			ck = self._ysp_ckey(vid, ts, guid, sdtfrom)
			if len(ck) < 20:
				time.sleep(0.3)
				continue
			params = {
				'guid':guid,'platform':sdtfrom,'vid':vid,'defn':defn,'charge':'0','defaultfmt':'auto',
				'otype':'json','defnpayver':'1','appVer':'1.2.3','sphttps':'1','sphls':'1','spwm':'4',
				'defsrc':'2','encryptVer':'8.1','sdtfrom':sdtfrom,'cKey':ck
				# 注意: 不传 dtype 才能拿到 MP4 直链(dltype:1, 含fvkey)
			}
			for _d in _YSF_DOMAINS:
				url = 'https://' + _d + '/playvinfo?' + urllib.parse.urlencode(params)
				req = urllib.request.Request(url, headers=FULL_HDRS)
				try:
					raw = urllib.request.urlopen(req, timeout=8, context=ctx).read().decode('utf-8', errors='replace')
				except Exception:
					continue
				s = raw.strip()
				if s.startswith('('): s = s[1:]
				if s.endswith(')'): s = s[:-1]
				s = s.strip().rstrip(';').strip()
				try:
					jo = json.loads(s)
				except Exception:
					continue
				# exem: 0=正常; 2=带有效vl的档位响应(综艺期次常返回2而非0); 其它(如-12=无此档)丢弃
				if jo.get('exem', -1) not in (0, 2):
					continue
				try:
					vi = jo['vl']['vi'][0]
					base = vi['ul']['ui'][0]['url'].rstrip('/') + '/'
					fn = vi['fn']
					fvkey = vi['fvkey']
					# 720P硬约束: 若服务端提供了宽高且低于720, 丢弃并按下一档(或下一attempt)重试
					_vh = vi.get('vh') or 0
					if _vh and _vh < 720:
						continue
				except Exception:
					continue
				return base + fn + '?vkey=' + fvkey + '&sdtfrom=' + sdtfrom + '&guid=' + guid
			time.sleep(0.4 * (attempt + 1))
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
		# 档位轮询 shd->fhd->sd: 免费剧首档即返回False快速定论; 遇有效档无完整流即返回True
		import random, string, ssl, urllib.request, urllib.parse, time, json
		sdtfrom = '4330701'
		_DEFNS = ['shd', 'fhd', 'sd']
		UAS = [
			"Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
			"Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
		]
		ctx = ssl._create_unverified_context()
		for attempt in range(2):
			for defn in _DEFNS:
				try:
					guid = 'mu1ja7md_' + ''.join(random.choice(string.ascii_letters+string.digits) for _ in range(18))
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