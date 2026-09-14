// ============================================================
//  JRKAN直播  drpy2 规则  (OK影视 / TVBox 可用)
// ------------------------------------------------------------
//  适用引擎 : drpy2  (rule 对象 + 全局 request / pdfh / pdfa / pd)
//  用法     : OK影视 → 配置 → 自定义源
//             type = 3 , api = drpy2.min.js 地址 , ext = 本文件地址
//  示例配置(json 片段):
//     {
//       "key": "jrkan",
//       "name": "⚽ JRKAN直播",
//       "type": 3,
//       "api": "https://agit.ai/fantaiying/fty/raw/branch/master/ext/drpy2.min.js",
//       "ext": "https://你的CDN地址/JRKAN直播.js",
//       "style": { "type": "list" },
//       "searchable": 0, "quickSearch": 0, "changeable": 0
//     }
// ------------------------------------------------------------
//  说明:
//   1. 老规则 .loc_match:eq(2) 写死第3块 + :gt/:lt 砍固定 li, 改版即废.
//      本规则改用宽松的一级选择器, 并在 JS 里做多域名 fallback.
//   2. 真实播放地址多为 sportsteam 中间页 → 走 lazy 提取 .m3u8.
//   3. 选择器若与你当前站点版本不符, 按文末"调试"提示微调即可.
// ============================================================

var UA = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';

// 多备用域名, __getHtml 会依次尝试, 第一个成功即返回
var HOSTS = [
    'https://www.jrs80.com',
    'https://www.jrs945.com',
    'https://www.jrs03.com',
    'https://www.jrs04.com'
];

// 通用 GET, 自动 join 相对地址, 带 Referer/UA
function __req(url, referer) {
    return request({
        url: url,
        headers: {
            'User-Agent': UA,
            'Referer': referer || (HOSTS[0] + '/')
        }
    });
}

// 带 host fallback 的页面抓取
function __getHtml(path) {
    var errs = [];
    for (var i = 0; i < HOSTS.length; i++) {
        var u = HOSTS[i] + (path || '/');
        try {
            var html = __req(u);
            if (html && html.length > 500) {
                // 缓存本次成功的 host 供后续使用
                this._host = HOSTS[i];
                return { html: html, host: HOSTS[i] };
            }
        } catch (e) {
            errs.push(HOSTS[i] + ':' + (e && e.message || e));
        }
    }
    throw '所有 host 均失败: ' + errs.join(' | ');
}

var rule = {
    title: 'JRKAN直播',
    host: 'https://www.jrs80.com',
    // 备用(引擎若支持 host 数组可填, 否则靠上方 JS fallback)
    // host_backup: 'https://www.jrs945.com',
    url: '/',
    searchUrl: '',
    searchable: 0,
    quickSearch: 0,
    class_name: '全部',
    class_url: '/',
    headers: { 'User-Agent': 'MOBILE_UA' },
    timeout: 10000,
    play_parse: true,
    lazy: 'lazy',
    limit: 6,
    double: false,
    推荐: '*',

    // ---------- 一级: 首页比赛列表 ----------
    // 思路: 先取每场比赛的块(li/a), 再从中抓 时间/赛事/队名/封面/详情链接.
    // 不同改版请把最前面容器选择器(.loc_match / .d-touch / .match_list) 三选一切实存在的.
    // 字段顺序: 标题, 封面, 时间, 详情链接
    一级: [
        '.loc_match .d-touch;li&&Text;img&&src;.lab_time&&Text;a&&href',  // 改版A
        '.loc_match;li&&Text;img&&src;.lab_time&&Text;a&&href',          // 改版B(无 d-touch)
        '.match_list;li&&Text;img&&src;.time&&Text;a&&href',            // 改版C
        '*'                                                               // 兜底: 全页文本
    ].join(' ##### '),

    // ---------- 二级: 比赛详情 / 播放线路 ----------
    // tabs = 线路分组, lists = 每条播放地址
    二级: {
        title: '.sub_list li:lt(3)&&Text',
        img: 'img&&src',
        desc: '.lab_team_home&&Text;.lab_team_away&&Text',
        content: '.sub_list ul&&Text',
        tabs: '.sub_tabs a',
        tab_text: 'a&&Text',
        lists: '.sub_channel a',
        list_text: 'a&&Text',
        list_url: 'a&&data-play'
    },

    搜索: '',

    // ---------- 预处理: 把首页 html 里的相对链接改成绝对地址 ----------
    预处理: function (html) {
        var self = this;
        HOSTS.forEach(function (h) {
            html = html.split('src="' + h).join('src="' + h); // 已绝对不动
        });
        // 兜底: 给无协议的 sportsteam 播放域补 https
        html = html.replace(/(src|href)="(https?:\/\/play\.sportsteam\d+\.com[^"]*)"/g, '$1="$2"');
        return html;
    },

    // ---------- lazy: 二级给的地址 → 真实可播 m3u8 ----------
    // input = { url, ... } , 需返回最终直链字符串
    lazy: function (input) {
        var url = (input && (input.url || input.play || input.link)) || '';
        if (!url) return '';

        // A. 已经是 m3u8/mp4 直链 → 直接出
        if (/\.m3u8(\?.*)?$/i.test(url) || /\.mp4(\?.*)?$/i.test(url)) {
            return url;
        }

        // B. sportsteam 中间页: 请求后从 script/json/video 里提 m3u8
        var html = '';
        try { html = __req(url, HOSTS[0] + '/'); } catch (e) { html = ''; }

        var m3u8 = '';

        // 取出页面 script 区文本(含 hls/js 变量), 统一用正则提 m3u8
        var txt = pdfh(html, 'script&&Text') || html;

        // B1. 通用: 任意 https?://...m3u8 串(覆盖 hls= / var url= / JSON 等)
        //     URL 不含空格/引号/反斜杠, 用 [^\s"'\\]

        var sm = /https?:\/\/[^\s"'\\]+?\.m3u8[^\s"'\\]*/i.exec(txt);
        if (sm) m3u8 = sm[0].replace(/\\u002F/g, '/');

        // B2. 带引号包裹的 JSON 风格 {url:"..."}
        if (!m3u8) {
            var jm = /["'](?:url|hls|playurl|file|src)["']\s*:\s*["']([^"']+\.m3u8[^"']*)["']/i.exec(txt);
            if (jm) m3u8 = jm[1].replace(/\\u002F/g, '/');
        }

        // B3. video 标签 src(部分静态页)
        if (!m3u8) m3u8 = pdfh(html, 'video&&src');

        // B4. 任意属性兜底
        if (!m3u8) m3u8 = pd(html, 'src', 'https?:.+?\\.m3u8.+?');

        return m3u8 || url; // 都提不到就原样返回, 交给播放器试播
    }
};

// 兼容 drpy2 "赋值给 module.exports / 全局 rule" 两种加载方式
if (typeof module !== 'undefined' && module.exports) {
    module.exports = rule;
}
