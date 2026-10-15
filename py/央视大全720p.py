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
import random
import string
import ssl

class Spider(Spider):
	def getName(self):
		return "中央电视台"
	def init(self,extend=""):
		print("============{0}============".format(extend))
		pass
	def destroy(self):
		pass
	def isVideoFormat(self,url):
		pass
	def manualVideoCheck(self):
		pass

	# ==================== 首页分类 ====================
	def homeContent(self,filter):
		result = {}
		cateManual = {
			"央视大全":"节目大全",
			"电视剧":"电视剧",
			"动画片":"动画片",
			"纪录片":"纪录片",
			"特别节目":"特别节目"
		}
		classes = []
		for k in cateManual:
			classes.append({'type_name':k,'type_id':cateManual[k]})
		result['class'] = classes
		if filter:
			result['filters'] = self.config['filter']
		return result

	def homeVideoContent(self):
		return {'list':[]}

	# ==================== 分类列表 ====================
	def categoryContent(self,tid,pg,filter,extend):
		result = {}
		year = ""; area=''; channel=''; datafl=''; letter=''
		pagecount=24
		if tid=='动画片':
			id=urllib.parse.quote(tid)
			if 'datadq-area' in extend: area=urllib.parse.quote(extend['datadq-area'])
			if 'dataszm-letter' in extend: letter=extend['dataszm-letter']
			if 'datafl-sc' in extend: datafl=urllib.parse.quote(extend['datafl-sc'])
			url='https://api.cntv.cn/list/getVideoAlbumList?channelid=CHAL1460955899450127&area={0}&sc={4}&fc={1}&letter={2}&p={3}&n=24&serviceId=tvcctv&topv=1&t=json'.format(area,id,letter,pg,datafl)
		elif tid=='纪录片':
			id=urllib.parse.quote(tid)
			if 'datapd-channel' in extend: channel=urllib.parse.quote(extend['datapd-channel'])
			if 'datafl-sc' in extend: datafl=urllib.parse.quote(extend['datafl-sc'])
			if 'datanf-year' in extend: year=extend['datanf-year']
			if 'dataszm-letter' in extend: letter=extend['dataszm-letter']
			url='https://api.cntv.cn/list/getVideoAlbumList?channelid=CHAL1460955924871139&fc={0}&channel={1}&sc={2}&year={3}&letter={4}&p={5}&n=24&serviceId=tvcctv&topv=1&t=json'.format(id,channel,datafl,year,letter,pg)
		elif tid=='电视剧':
			id=urllib.parse.quote(tid)
			if 'datafl-sc' in extend: datafl=urllib.parse.quote(extend['datafl-sc'])
			if 'datanf-year' in extend: year=extend['datanf-year']
			if 'dataszm-letter' in extend: letter=extend['dataszm-letter']
			url='https://api.cntv.cn/list/getVideoAlbumList?channelid=CHAL1460955853485115&area={0}&sc={1}&fc={2}&year={3}&letter={4}&p={5}&n=24&serviceId=tvcctv&topv=1&t=json'.format(area,datafl,id,year,letter,pg)
		elif tid=='特别节目':
			id=urllib.parse.quote(tid)
			if 'datapd-channel' in extend: channel=urllib.parse.quote(extend['datapd-channel'])
			if 'datafl-sc' in extend: datafl=urllib.parse.quote(extend['datafl-sc'])
			if 'dataszm-letter' in extend: letter=extend['dataszm-letter']
			url='https://api.cntv.cn/list/getVideoAlbumList?channelid=CHAL1460955953877151&channel={0}&sc={1}&fc={2}&bigday=&letter={3}&p={4}&n=24&serviceId=tvcctv&topv=1&t=json'.format(channel,datafl,id,letter,pg)
		elif tid=='节目大全':
			cid=extend.get('cid',''); fc=extend.get('fc',''); fl=extend.get('fl','')
			url='https://api.cntv.cn/lanmu/columnSearch?&fl={0}&fc={1}&cid={2}&p={3}&n=20&serviceId=tvcctv&t=json&cb=ko'.format(fl,fc,cid,pg)
			pagecount=20
		else:
			url='https://tv.cctv.com/epg/index.shtml'

		videos=[]
		try:
			htmlText=self.webReadFile(urlStr=url,header=self.header)
			if tid=='节目大全':
				idx=htmlText.rfind(');')
				if idx>-1:
					videos=self.get_list1(html=htmlText[3:idx],tid=tid)
			else:
				videos=self.get_list(html=htmlText,tid=tid)
		except Exception:
			pass

		result['list']=videos
		result['page']=pg
		result['pagecount']=9999 if len(videos)>=pagecount else pg
		result['limit']=90
		result['total']=999999
		return result

	# ==================== 详情 ====================
	def detailContent(self,array):
		aid=array[0].split('###')
		tid=aid[0]; logo=aid[3]; lastVideo=aid[2]; title=aid[1]
		id=aid[4]; vod_year=aid[5]; actors=aid[6]; brief=aid[7]
		fromId='CCTV'
		videoList=[]

		try:
			if tid=="搜索":
				fromId='中央台'
				videoList=[title+"$"+lastVideo]
			elif tid=="节目大全":
				# 节目大全：优先走央视频 vid（若已落 vid 则直接出 720P）
				# lastVideo 这里约定：若是 ysp_xxx 则直接使用
				if lastVideo.startswith('ysp_'):
					videoList=[title+"$"+lastVideo]
				else:
					lastUrl='https://api.cntv.cn/video/videoinfoByGuid?guid={0}&serviceId=tvcctv'.format(id)
					topicId=json.loads(self.webReadFile(urlStr=lastUrl,header=self.header))['ctid']
					Url="https://api.cntv.cn/NewVideo/getVideoListByColumn?id={0}&d=&p=1&n=100&sort=desc&mode=0&serviceId=tvcctv&t=json".format(topicId)
					videoList=self._parse_album(self.webReadFile(urlStr=Url,header=self.header))
			else:
				# 普通分类：优先把每集 guid 换成央视频 vid（若拿得到）
				Url='https://api.cntv.cn/NewVideo/getVideoListByAlbumIdNew?id={0}&serviceId=tvcctv&p=1&n=100&mode=0&pub=1'.format(id)
				videoList=self._parse_album(self.webReadFile(urlStr=Url,header=self.header), prefer_ysp=True, title=title)
		except Exception:
			pass

		if not videoList:
			# 兜底：单集
			videoList=[title+"$"+('ysp_'+id if False else lastVideo)]

		vod={
			"vod_id":array[0],
			"vod_name":title,
			"vod_pic":logo,
			"type_name":tid,
			"vod_year":vod_year,
			"vod_area":"",
			"vod_remarks":"",
			"vod_actor":actors,
			"vod_director":"",
			"vod_content":brief,
			"vod_play_from":fromId,
			"vod_play_url":"#".join(videoList)
		}
		return {'list':[vod]}

	def _parse_album(self,html,prefer_ysp=False,title=""):
		"""把专辑 json 转成 标题$播放地址；prefer_ysp 时尝试换 vid"""
		j=json.loads(html)
		videoList=[]
		for v in (j.get('data') or {}).get('list') or []:
			t=v.get('title','')
			guid=v.get('guid','')
			if not guid: continue
			if prefer_ysp:
				vid=self._cntv_guid_to_ysp_vid(guid, hint=title)
				if vid:
					videoList.append(t+"$ysp_"+vid)
					continue
			videoList.append(t+"$"+guid)
		return videoList

	# ==================== 搜索 ====================
	def searchContent(self,key,quick):
		return self.searchContentPage(key,quick,'1')
	def searchContentPage(self,key,quick,page):
		key=urllib.parse.quote(key)
		Url='https://search.cctv.com/ifsearch.php?page=1&qtext={0}&sort=relevance&pageSize=20&type=video&vtime=-1&datepid=1&channel=&pageflag=0&qtext_str={0}'.format(key)
		htmlTxt=self.webReadFile(urlStr=Url,header=self.header)
		return {'list':self.get_list_search(htmlTxt,tid='搜索')}

	# ==================== 播放（核心：直接用 vid）====================
	def playerContent(self,flag,id,vipFlags):
		headers={
			'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
			'Referer':'https://v.yangshipin.cn/'
		}
		# 1) 直接是央视频 vid：跳过一切映射
		if isinstance(id,str) and id.startswith('ysp_'):
			mp4=self.get_ysp_mp4(id[4:])
			if mp4:
				return {"parse":0,"playUrl":"","url":mp4,"header":headers,"format":"video/mp4"}
			return {"parse":0,"playUrl":"","url":"","header":headers}

		# 2) 兼容：老数据是 guid，尝试一次 vid（不强制）
		if re.match(r'^[0-9a-f]{32}$', id):
			vid=self._cntv_guid_to_ysp_vid(id)
			if vid:
				mp4=self.get_ysp_mp4(vid)
				if mp4:
					return {"parse":0,"playUrl":"","url":mp4,"header":headers,"format":"video/mp4"}

		# 3) 兜底 m3u8
		return {"parse":0,"playUrl":"","url":self.get_m3u8(id),"header":headers}

	# ==================== 配置 ====================
	config = {
		"player":{},
		"filter":{
		"电视剧":[
		{"key":"datafl-sc","name":"类型","value":[{"n":"全部","v":""},{"n":"谍战","v":"谍战"},{"n":"悬疑","v":"悬疑"},{"n":"刑侦","v":"刑侦"},{"n":"历史","v":"历史"},{"n":"古装","v":"古装"},{"n":"武侠","v":"武侠"},{"n":"军旅","v":"军旅"},{"n":"战争","v":"战争"},{"n":"喜剧","v":"喜剧"},{"n":"青春","v":"青春"},{"n":"言情","v":"言情"},{"n":"偶像","v":"偶像"},{"n":"家庭","v":"家庭"},{"n":"年代","v":"年代"},{"n":"革命","v":"革命"},{"n":"农村","v":"农村"},{"n":"都市","v":"都市"},{"n":"其他","v":"其他"}]},
		{"key":"datadq-area","name":"地区","value":[{"n":"全部","v":""},{"n":"中国大陆","v":"中国大陆"},{"n":"中国香港","v":"香港"},{"n":"美国","v":"美国"},{"n":"欧洲","v":""}]},
		{"key":"datanf-year","name":"年份","value":[{"n":"全部","v":""},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"},{"n":"2007","v":"2007"},{"n":"2006","v":"2006"},{"n":"2005","v":"2005"},{"n":"2004","v":"2004"},{"n":"2003","v":"2003"},{"n":"2002","v":"2002"},{"n":"2001","v":"2001"},{"n":"2000","v":"2000"}]},
		{"key":"dataszm-letter","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"},{"n":"0-9","v":"0-9"}]}
		],
		"动画片":[
		{"key":"datafl-sc","name":"类型","value":[{"n":"全部","v":""},{"n":"亲子","v":"亲子"},{"n":"搞笑","v":"搞笑"},{"n":"冒险","v":"冒险"},{"n":"动作","v":"动作"},{"n":"益智","v":"益智"},{"n":"历史","v":"历史"},{"n":"教育","v":"教育"},{"n":"校园","v":"校园"},{"n":"言情","v":"言情"},{"n":"武侠","v":"武侠"},{"n":"经典","v":"经典"},{"n":"未来","v":"未来"},{"n":"古代","v":"古代"},{"n":"神话","v":"神话"},{"n":"真人","v":"真人"},{"n":"励志","v":"励志"},{"n":"热血","v":"热血"},{"n":"奇幻","v":"奇幻"},{"n":"童话","v":"童话"},{"n":"剧情","v":"剧情"},{"n":"其他","v":"其他"}]},
		{"key":"datadq-area","name":"地区","value":[{"n":"全部","v":""},{"n":"中国大陆","v":"中国大陆"},{"n":"美国","v":"美国"},{"n":"欧洲","v":"欧洲"}]},
		{"key":"dataszm-letter","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"},{"n":"0-9","v":"0-9"}]}
		],
		"纪录片":[
		{"key":"datapd-channel","name":"频道","value":[{"n":"全部","v":""},{"n":"CCTV1 综合","v":"CCTV1 综合"},{"n":"CCTV2 财经","v":"CCTV2 财经"},{"n":"CCTV3 综艺","v":"CCTV3 综艺"},{"n":"CCTV4 中文国际","v":"CCTV4 中文国际"},{"n":"CCTV5 体育","v":"CCTV5 体育"},{"n":"CCTV6 电影","v":"CCTV6 电影"},{"n":"CCTV7 国防军事","v":"CCTV7 国防军事"},{"n":"CCTV8 电视剧","v":"CCTV8 电视剧"},{"n":"CCTV9 纪录","v":"CCTV9 纪录"},{"n":"CCTV10 科教","v":"CCTV10 科教"},{"n":"CCTV11 戏曲","v":"CCTV11 戏曲"},{"n":"CCTV12 社会与法","v":"CCTV12 社会与法"},{"n":"CCTV13 新闻","v":"CCTV13 新闻"},{"n":"CCTV14 少儿","v":"CCTV14 少儿"},{"n":"CCTV15 音乐","v":"CCTV15 音乐"},{"n":"CCTV17 农业农村","v":"CCTV17 农业农村"}]},
		{"key":"datafl-sc","name":"类型","value":[{"n":"全部","v":""},{"n":"人文历史","v":"人文历史"},{"n":"人物","v":"人物"},{"n":"军事","v":"军事"},{"n":"探索","v":"探索"},{"n":"社会","v":"社会"},{"n":"时政","v":"时政"},{"n":"经济","v":"经济"},{"n":"科技","v":"科技"}]},
		{"key":"datanf-year","name":"年份","value":[{"n":"全部","v":""},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"},{"n":"2016","v":"2016"},{"n":"2015","v":"2015"},{"n":"2014","v":"2014"},{"n":"2013","v":"2013"},{"n":"2012","v":"2012"},{"n":"2011","v":"2011"},{"n":"2010","v":"2010"},{"n":"2009","v":"2009"},{"n":"2008","v":"2008"}]},
		{"key":"dataszm-letter","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"},{"n":"0-9","v":"0-9"}]}
		],
		"特别节目":[
		{"key":"datapd-channel","name":"频道","value":[{"n":"全部","v":""},{"n":"CCTV1 综合","v":"CCTV1 综合"},{"n":"CCTV2 财经","v":"CCTV2 财经"},{"n":"CCTV3 综艺","v":"CCTV3 综艺"},{"n":"CCTV4 中文国际","v":"CCTV4 中文国际"},{"n":"CCTV5 体育","v":"CCTV5 体育"},{"n":"CCTV6 电影","v":"CCTV6 电影"},{"n":"CCTV7 国防军事","v":"CCTV7 国防军事"},{"n":"CCTV8 电视剧","v":"CCTV8 电视剧"},{"n":"CCTV9 纪录","v":"CCTV9 纪录"},{"n":"CCTV10 科教","v":"CCTV10 科教"},{"n":"CCTV11 戏曲","v":"CCTV11 戏曲"},{"n":"CCTV12 社会与法","v":"CCTV12 社会与法"},{"n":"CCTV13 新闻","v":"CCTV13 新闻"},{"n":"CCTV14 少儿","v":"CCTV14 少儿"},{"n":"CCTV15 音乐","v":"CCTV15 音乐"},{"n":"CCTV17 农业农村","v":"CCTV17 农业农村"}]},
		{"key":"datafl-sc","name":"类型","value":[{"n":"全部","v":""},{"n":"新闻","v":"新闻"},{"n":"综艺","v":"综艺"},{"n":"体育","v":"体育"},{"n":"军事","v":"军事"},{"n":"影视","v":"影视"},{"n":"科教","v":"科教"},{"n":"戏曲","v":"戏曲"},{"n":"青少","v":"青少"},{"n":"音乐","v":"音乐"},{"n":"社会","v":"社会"},{"n":"公益","v":"公益"},{"n":"其他","v":"其他"}]},
		{"key":"dataszm-letter","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"},{"n":"0-9","v":"0-9"}]}
		],
		"节目大全":[
		{"key":"cid","name":"频道","value":[{"n":"全部","v":""},{"n":"CCTV-1综合","v":"EPGC1386744804340101"},{"n":"CCTV-2财经","v":"EPGC1386744804340102"},{"n":"CCTV-3综艺","v":"EPGC1386744804340103"},{"n":"CCTV-4中文国际","v":"EPGC1386744804340104"},{"n":"CCTV-5体育","v":"EPGC1386744804340107"},{"n":"CCTV-6电影","v":"EPGC1386744804340108"},{"n":"CCTV-7国防军事","v":"EPGC1386744804340109"},{"n":"CCTV-8电视剧","v":"EPGC1386744804340110"},{"n":"CCTV-9纪录","v":"EPGC1386744804340112"},{"n":"CCTV-10科教","v":"EPGC1386744804340113"},{"n":"CCTV-11戏曲","v":"EPGC1386744804340114"},{"n":"CCTV-12社会与法","v":"EPGC1386744804340115"},{"n":"CCTV-13新闻","v":"EPGC1386744804340116"},{"n":"CCTV-14少儿","v":"EPGC1386744804340117"},{"n":"CCTV-15音乐","v":"EPGC1386744804340118"},{"n":"CCTV-16奥林匹克","v":"EPGC1634630207058998"},{"n":"CCTV-17农业农村","v":"EPGC1563932742616872"}]},
		{"key":"fc","name":"分类","value":[{"n":"全部","v":""},{"n":"新闻","v":"新闻"},{"n":"体育","v":"体育"},{"n":"综艺","v":"综艺"},{"n":"健康","v":"健康"},{"n":"生活","v":"生活"},{"n":"科教","v":"科教"},{"n":"经济","v":"经济"},{"n":"农业","v":"农业"},{"n":"法治","v":"法治"},{"n":"军事","v":"军事"},{"n":"少儿","v":"少儿"},{"n":"动画","v":"动画"},{"n":"纪实","v":"纪实"},{"n":"戏曲","v":"戏曲"},{"n":"音乐","v":"音乐"},{"n":"影视","v":"影视"}]},
		{"key":"fl","name":"字母","value":[{"n":"全部","v":""},{"n":"A","v":"A"},{"n":"B","v":"B"},{"n":"C","v":"C"},{"n":"D","v":"D"},{"n":"E","v":"E"},{"n":"F","v":"F"},{"n":"G","v":"G"},{"n":"H","v":"H"},{"n":"I","v":"I"},{"n":"J","v":"J"},{"n":"K","v":"K"},{"n":"L","v":"L"},{"n":"M","v":"M"},{"n":"N","v":"N"},{"n":"O","v":"O"},{"n":"P","v":"P"},{"n":"Q","v":"Q"},{"n":"R","v":"R"},{"n":"S","v":"S"},{"n":"T","v":"T"},{"n":"U","v":"U"},{"n":"V","v":"V"},{"n":"W","v":"W"},{"n":"X","v":"X"},{"n":"Y","v":"Y"},{"n":"Z","v":"Z"}]}
		]
		}
		}
	}
	header={
		"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36",
		"Host":"tv.cctv.com",
		"Referer":"https://tv.cctv.com/"
	}

	# ==================== 工具函数 ====================
	def webReadFile(self,urlStr,header):
		req=urllib.request.Request(url=urlStr)
		with urllib.request.urlopen(req) as response:
			return response.read().decode('utf-8')
	def TestWebPage(self,urlStr,header):
		req=urllib.request.Request(url=urlStr,method='HEAD')
		with urllib.request.urlopen(req) as response:
			return response.getcode()
	def get_RegexGetText(self,Text,RegexText,Index):
		m=re.search(RegexText,Text,re.M|re.S)
		return m.group(Index) if m else ""
	def get_EpisodesList(self,jsonList):
		return [v['title']+"$"+v['guid'] for v in jsonList if v.get('guid')]
	def get_EpisodesList_re(self,htmlTxt,patternTxt):
		return [m.group('title')+"$"+m.group('url') for m in re.finditer(patternTxt,htmlTxt,re.M|re.S)]
	def get_lineList(self,Txt,mark,after):
		out=[]; i=Txt.find(mark)
		while i>8:
			e=Txt.find(after,i); out.append(Txt[i:e]); i=Txt.find(mark,e)
		return out
	def get_RegexGetTextLine(self,Text,RegexText,Index):
		return re.findall(RegexText,Text,re.M|re.S) or []
	def removeHtml(self,txt):
		return re.sub(r'<[^>]+>','',txt).replace("&nbsp;"," ")
	def get_m3u8(self,urlTxt):
		try:
			jo=json.loads(self.webReadFile("https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid={0}".format(urlTxt),self.header))
			link=jo['hls_url'].strip()
			arr=self.webReadFile(link,self.header).strip().split('\n')
			prefix=re.search(r'(http[s]?://[a-zA-z0-9.]+)/',link).group(1)
			sub=arr[-1].split('/'); sub[3]='2000'; sub[-1]='2000.m3u8'
			hd=prefix+'/'.join(sub)
			if self.TestWebPage(hd,self.header)==200:
				return hd
			return prefix+arr[-1]
		except Exception:
			return ""

	# 搜索结果
	def get_list_search(self,html,tid):
		videos=[]
		for v in json.loads(html).get('list') or []:
			url=v.get('urllink',''); title=self.removeHtml(v.get('title',''))
			if not url: continue
			videos.append({"vod_id":"{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,v.get('imglink',''),v.get('id',''),v.get('uploadtime',''),'',v.get('channel','')),"vod_name":title,"vod_pic":v.get('imglink',''),"vod_remarks":v.get('uploadtime','')})
		return videos
	# 节目大全
	def get_list1(self,html,tid):
		videos=[]
		for v in (json.loads(html).get('response') or {}).get('docs') or []:
			lv=v.get('lastVIDE') or {}
			id=lv.get('videoSharedCode',''); title=v.get('column_name',''); url=v.get('column_website','')
			if not id or not url: continue
			videos.append({"vod_id":"{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,v.get('column_logo',''),id,v.get('column_playdate',''),'',v.get('column_brief','')),"vod_name":title,"vod_pic":v.get('column_logo',''),"vod_remarks":''})
		return videos
	# 分类
	def get_list(self,html,tid):
		videos=[]
		for v in (json.loads(html).get('data') or {}).get('list') or []:
			url=v.get('url',''); title=v.get('title','')
			if not url: continue
			videos.append({"vod_id":"{0}###{1}###{2}###{3}###{4}###{5}###{6}###{7}".format(tid,title,url,v.get('image',''),v.get('id',''),v.get('year',''),v.get('actors',''),v.get('brief','')),"vod_name":title,"vod_pic":v.get('image',''),"vod_remarks":''})
		return videos

	# ==================== 央视频 vid 取流（核心）====================
	def _cntv_guid_to_ysp_vid(self,guid,hint=""):
		"""可选辅助：仅在新数据没有 vid 时做一次映射；不影响主链路"""
		try:
			ctx=ssl._create_unverified_context()
			v=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.cntv.cn/video/videoinfoByGuid?guid=%s&serviceId=tvcctv'%guid,headers={'User-Agent':'Mozilla/5.0'}),timeout=15,context=ctx).read().decode('utf-8','replace'))
			title=re.sub(r'[《》\d]','',v.get('title','')).strip() or hint
			if not title: return None
			qs=urllib.parse.quote(title.split(' ')[0])
			req=urllib.request.Request("https://csapi.yangshipin.cn/voapi/omsotm/v2/search?type=0&query=%s&page=1&size=5"%qs,headers={"yspappid":"539073109","platform":"109","app-platform":"m","app-version":"1.0.0","User-Agent":"Mozilla/5.0"})
			raw=urllib.request.urlopen(req,timeout=20,context=ctx).read().decode('utf-8','replace')
			m=re.search(r'"vid"\s*:\s*"([a-z0-9]{10,})"',raw)
			return m.group(1) if m else None
		except Exception:
			return None

	# ============ AES-128-CBC（纯Python，无依赖）============
	_SBOX=[0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
	_RCON=[0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]
	def _gf_mul(self,a,b):
		r=0
		for _ in range(8):
			if b&1: r^=a
			hi=a&0x80; a=(a<<1)&0xff
			if hi: a^=0x1b
			b>>=1
		return r
	def _expand_key(self,key):
		w=[[key[4*i+j] for j in range(4)] for i in range(4)]
		for i in range(4,44):
			t=list(w[i-1])
			if i%4==0:
				t=t[1:]+t[:1]; t=[self._SBOX[b] for b in t]; t[0]^=self._RCON[i//4-1]
			w.append([w[i-4][j]^t[j] for j in range(4)])
		return w
	def _aes_encrypt_block(self,block,w):
		s=[[block[r+4*c] for c in range(4)] for r in range(4)]
		def add(rnd):
			for c in range(4):
				for r in range(4): s[r][c]^=w[4*rnd+c][r]
		add(0)
		for rnd in range(1,10):
			for r in range(4):
				for c in range(4): s[r][c]=self._SBOX[s[r][c]]
			for r in range(1,4): s[r]=s[r][r:]+s[r][:r]
			for c in range(4):
				a,b,c_,d=s[0][c],s[1][c],s[2][c],s[3][c]
				s[0][c]=self._gf_mul(2,a)^self._gf_mul(3,b)^c_^d
				s[1][c]=a^self._gf_mul(2,b)^self._gf_mul(3,c_)^d
				s[2][c]=a^b^self._gf_mul(2,c_)^self._gf_mul(3,d)
				s[3][c]=self._gf_mul(3,a)^b^c_^self._gf_mul(2,d)
			add(rnd)
		for r in range(4):
			for c in range(4): s[r][c]=self._SBOX[s[r][c]]
		for r in range(1,4): s[r]=s[r][r:]+s[r][:r]
		add(10)
		return bytes(s[r][c] for c in range(4) for r in range(4))
	def _aes_cbc_encrypt(self,key,iv,plain):
		w=self._expand_key(key); pad=16-(len(plain)%16); plain+=bytes([pad])*pad
		out=b""; prev=iv
		for i in range(0,len(plain),16):
			e=self._aes_encrypt_block(bytes(plain[i+j]^prev[j] for j in range(16)),w); out+=e; prev=e
		return out
	def _ysp_ckey(self,vid,ts,guid,sdtfrom='4330701'):
		Tt='4E2918885FD98109869D14E0231A0BF4'; At='16B17E519DDD0CE5B79D7A63A4DD801C'
		sr='mg3c3b04ba'; appVer='1.2.3'; Un='https://www.yangshipin.c'; Mn='node.js/24'; zn='https://www.baidu.com/'
		Hn='undefined'; Bn='undefined'; Gn='Linux arm64'
		Fn=('|'+vid+'|'+str(ts)+'|'+sr+'|'+appVer+'|'+guid+'|'+str(sdtfrom)+'|'+Un+'|'+Mn+'|'+zn+'|'+Hn+'|'+Bn+'|'+Gn+'|')
		Yn=0
		for ch in Fn: Yn=(Yn<<5)-Yn+ord(ch)&0xFFFFFFFF
		Xn='|'+str(Yn)+Fn
		return '--01'+self._aes_cbc_encrypt(bytes.fromhex(Tt),bytes.fromhex(At),Xn.encode('utf-8')).hex().upper()

	def get_ysp_mp4(self,vid):
		"""直接用央视频 vid 取 720P MP4 直链，绝不走 guid 映射"""
		sdtfrom='4330701'
		_DEFNS=['shd','fhd','sd']
		_UA=("Mozilla/5.0 (iPhone; CPU iPhone OS %s like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/%s Mobile/15E148 Safari/604.1")
		_VERS=[('16_0','16.0'),('16_6','16.6'),('15_5','15.5'),('17_0','17.0'),('17_4','17.4')]
		HDRS={'Referer':'https://v.yangshipin.cn/','yspappid':'539073109','platform':'109','app-platform':'m','app-version':'1.0.0','Accept':'*/*','Connection':'keep-alive'}
		ctx=ssl._create_unverified_context()
		DOMAINS=['playvv.yangshipin.cn','playvv.ysp.cctv.cn','bkplayvv.ysp.cctv.cn','playvv6.ysp.cctv.cn']
		for a in range(6):
			defn=_DEFNS[a%len(_DEFNS)]; HDRS['User-Agent']=_UA%_VERS[a%len(_VERS)]
			guid='mu1ja7md_'+''.join(random.choice(string.ascii_letters+string.digits) for _ in range(18))
			ck=self._ysp_ckey(vid,int(time.time()),guid,sdtfrom)
			if len(ck)<20: time.sleep(0.3); continue
			params={'guid':guid,'platform':sdtfrom,'vid':vid,'defn':defn,'charge':'0','defaultfmt':'auto','otype':'json','defnpayver':'1','appVer':'1.2.3','sphttps':'1','sphls':'1','spwm':'4','defsrc':'2','encryptVer':'8.1','sdtfrom':sdtfrom,'cKey':ck}
			for d in DOMAINS:
				try:
					raw=urllib.request.urlopen(urllib.request.Request('https://'+d+'/playvinfo?'+urllib.parse.urlencode(params),headers=HDRS),timeout=8,context=ctx).read().decode('utf-8','replace')
				except Exception:
					continue
				s=raw.strip().strip('()').rstrip(';').strip()
				try: jo=json.loads(s)
				except Exception: continue
				if jo.get('exem',-1) not in (0,2): continue
				try:
					vi=jo['vl']['vi'][0]; base=vi['ul']['ui'][0]['url'].rstrip('/')+'/'; fn=vi['fn']; fvkey=vi['fvkey']
					if vi.get('vh',0)>=720:
						return base+fn+'?vkey='+fvkey+'&sdtfrom='+sdtfrom+'&guid='+guid
				except Exception: continue
			time.sleep(0.4*(a+1))
		return ''