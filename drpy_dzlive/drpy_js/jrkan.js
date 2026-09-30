var rule = {
    title: 'JRKAN直播',
    host: 'https://www.jrs04.com/',   // 当前主用，可换 jrs945 / jrs80
    url: '/',
    searchUrl: '',
    searchable: 0,
    quickSearch: 0,
    class_name: '全部',
    class_url: '/',
    headers: {
        'User-Agent': 'MOBILE_UA',
        'Referer': 'https://www.jrs04.com/'
    },
    timeout: 8000,
    play_parse: true,

    // ===== lazy：把相对路径拼成绝对地址，再进播放页提 m3u8 =====
    lazy: `js:
        let u = input;
        let base = 'https://www.jrs04.com';
        if(u.startsWith('/')) u = base + u;
        let hd = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
            'Referer': base + '/'
        };
        let html = request(u, hd);
        // 1) 直接找 m3u8
        let m = html.match(/https?:\\/\\/[^\\"'\\s]+?\\.m3u8[^\\"'\\s]*/);
        if(m) return m[0];
        // 2) 找 iframe 再套一层
        let f = html.match(/<iframe[^>]+src=["']([^"']+)["']/i);
        if(f){
            let fu = f[1];
            if(fu.startsWith('/')) fu = base + fu;
            let html2 = request(fu, hd);
            let m2 = html2.match(/https?:\\/\\/[^\\"'\\s]+?\\.m3u8[^\\"'\\s]*/);
            if(m2) return m2[0];
            return html2;
        }
        // 3) 有些是 var playurl="..." 形式
        let v = html.match(/var\\s+\\w+\\s*=\\s*["'](https?:[^"']+\\.m3u8[^"']*)["']/);
        if(v) return v[1];
        return u;
    `,

    limit: 6,
    double: false,
    推荐: '*',

    // ===== 一级：首页比赛列表 =====
    // 结构：.loc_match 下 ul.item 为单场，内部两队名+时间
    一级: '.loc_match ul.item;li.lab_team_home .name&&Text+ @ +li.lab_team_away .name&&Text;li .avatar img&&src;li.lab_time&&Text;a&&href',

    // ===== 二级：详情页选源 =====
    二级: {
        title: '.sub_channel a.item strong&&Text',
        img: '.lab_team_home .avatar img&&src',
        desc: '.lab_team_home .name&&Text;VS;.lab_team_away .name&&Text',
        content: '.lab_time&&Text',
        tabs: '',
        tab_text: '',
        lists: '.sub_channel a.item',
        list_text: 'strong&&Text',
        list_url: 'a&&data-play'   // 相对路径，交给 lazy 拼绝对地址+提流
    },

    搜索: ''
};
