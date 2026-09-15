import { Crypto } from 'assets://js/lib/cat.js';

let siteKey = '';
let siteType = 0;

const HOST = "https://v.qq.com";
const API_HOST = "https://pbaccess.video.qq.com";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36";

const DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Origin": HOST,
    "Referer": HOST + "/",
    "Accept": "application/json, text/plain, */*"
};

// 分类映射，对应原规则class_name
const CATE_MAP = {
    "choice": { name: "精选", cid: "" },
    "movie": { name: "电影", cid: "100173" },
    "tv": { name: "电视剧", cid: "100113" },
    "variety": { name: "综艺", cid: "100109" },
    "cartoon": { name: "动漫", cid: "110755" },
    "child": { name: "少儿", cid: "100150" },
    "doco": { name: "纪录片", cid: "100105" }
};

async function request(url, opt = {}) {
    try {
        const headers = Object.assign({}, DEFAULT_HEADERS, opt.headers || {});
        let postType = '';
        const ctype = headers['Content-Type'] || '';
        if (ctype.includes('json')) postType = 'json';
        else if (ctype.includes('form')) postType = 'form';
        const res = await req(url, {
            method: opt.method || "GET",
            headers: headers,
            data: opt.data,
            postType: postType,
            timeout: opt.timeout || 15000
        });
        return res?.content ?? "";
    } catch (e) {
        console.error("request error:", url, e?.message);
        return "";
    }
}

function safeJson(str) {
    try {
        if (!str) return null;
        if (typeof str === 'object') return str;
        return JSON.parse(str);
    } catch (e) {
        console.error("safeJson parse error", e.message);
        return null;
    }
}

function fixPicUrl(url) {
    if (!url) return '';
    url = url.trim();
    if (url.startsWith('http')) return url;
    if (url.startsWith('//')) return `https:${url}`;
    return HOST + url;
}

// 安全多层取值，防止数组越界崩溃
function safeGet(obj, ...keys) {
    let o = obj;
    for (const k of keys) {
        if (o === null || o === undefined) return undefined;
        if (Array.isArray(o)) {
            const idx = Number(k);
            if (idx < 0 || idx >= o.length) return undefined;
            o = o[idx];
        } else if (typeof o === "object") {
            o = o[k];
        } else {
            return undefined;
        }
    }
    return o;
}

function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

async function init(cfg) {
    try {
        siteKey = cfg.skey;
        siteType = cfg.stype;
    } catch (e) {
        console.error("init error", e.message);
    }
}

// home同步函数，输出主分类，筛选器这里做静态（规避原py多线程卡死问题）
function home(filter) {
    try {
        const classes = [];
        for (const key in CATE_MAP) {
            const item = CATE_MAP[key];
            if (item.cid) {
                classes.push({ type_id: item.cid, type_name: item.name });
            }
        }
        return JSON.stringify({ class: classes, filters: {} });
    } catch (e) {
        console.error("home error", e.message);
        return JSON.stringify({ class: [], filters: {} });
    }
}

async function homeVod() {
    try {
        const body = {
            "page_params": {
                "channel_id": "100173",
                "filter_params": "sort=75",
                "page_type": "channel_operation",
                "page_id": "channel_list_second_page"
            }
        };
        const raw = await request(`${API_HOST}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify(body),
            postType: "json"
        });
        const json = safeJson(raw);
        const itemList = safeGet(json, "data", "module_list_datas", -1, "module_datas", -1, "item_data_lists", "item_datas") || [];
        const list = [];
        for (const it of itemList) {
            const p = safeGet(it, "item_params") || {};
            const cid = p.cid;
            if (!cid) continue;
            const tagRaw = p.uni_imgtag || p.imgtag || "{}";
            const tag = safeJson(tagRaw) || {};
            list.push({
                vod_id: String(cid),
                vod_name: p.mz_title || p.title || "",
                vod_pic: fixPicUrl(p.new_pic_hz || p.new_pic_vt || ""),
                vod_year: safeGet(tag, "tag_2", "text") || "",
                vod_remarks: safeGet(tag, "tag_4", "text") || ""
            });
        }
        return JSON.stringify({ list: list.slice(0,18) });
    } catch (e) {
        console.error("homeVod error", e.message);
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, filter, ext) {
    pg = Number(pg) || 1;
    try {
        const extend = safeJson(ext) || {};
        const filterParamsObj = {
            sort: extend.sort || "75",
            attr: extend.attr || "-1",
            itype: extend.itype || "-1",
            ipay: extend.ipay || "-1",
            iarea: extend.iarea || "-1",
            iyear: extend.iyear || "-1",
            theater: extend.theater || "-1",
            award: extend.award || "-1",
            recommend: extend.recommend || "-1"
        };
        const filterStr = Object.entries(filterParamsObj).filter(([_,v])=>v!==undefined).map(([k,v])=>`${k}=${v}`).join("&");
        const body = {
            "page_params": {
                "channel_id": tid,
                "filter_params": filterStr,
                "page_type": "channel_operation",
                "page_id": "channel_list_second_page"
            }
        };
        if (pg > 1) {
            body.page_params.page_context = extend.page_context || "";
        }
        const raw = await request(`${API_HOST}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify(body),
            postType: "json"
        });
        const json = safeJson(raw);
        const ndata = safeGet(json, "data") || {};
        const hasNext = Boolean(ndata.has_next_page);
        const itemList = safeGet(ndata, "module_list_datas", -1, "module_datas", -1, "item_data_lists", "item_datas") || [];
        const list = [];
        for (const it of itemList) {
            const p = safeGet(it, "item_params") || {};
            const cid = p.cid;
            if (!cid) continue;
            const tagRaw = p.uni_imgtag || p.imgtag || "{}";
            const tag = safeJson(tagRaw) || {};
            list.push({
                vod_id: String(cid),
                vod_name: p.mz_title || p.title || "",
                vod_pic: fixPicUrl(p.new_pic_hz || p.new_pic_vt || ""),
                vod_year: safeGet(tag, "tag_2", "text") || "",
                vod_remarks: safeGet(tag, "tag_4", "text") || ""
            });
        }
        return JSON.stringify({
            list,
            page: pg,
            pagecount: hasNext ? 9999 : pg,
            limit: 90,
            total: 999999
        });
    } catch (e) {
        console.error("category error", e.message);
        return JSON.stringify({ list: [], page: pg, pagecount: 0 });
    }
}

async function detail(vodId) {
    try {
        const cid = String(vodId);
        const detailBody = {
            "page_params": {
                "req_from": "web",
                "cid": cid,
                "vid": "",
                "lid": "",
                "page_type": "detail_operation",
                "page_id": "detail_page_introduction"
            },
            "has_cache": 1
        };
        const epiBody = {
            "page_params": {
                "req_from": "web_vsite",
                "page_id": "vsite_episode_list",
                "page_type": "detail_operation",
                "id_type": "1",
                "cid": cid,
                "vid": "",
                "lid": "",
                "page_num": "",
                "page_context": "",
                "detail_page_type": "1"
            },
            "has_cache": 1
        };
        const rawDetail = await request(`${API_HOST}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96`, {
            method:"POST", headers:{"Content-Type":"application/json"}, data:JSON.stringify(detailBody), postType:"json"
        });
        const rawEpi = await request(`${API_HOST}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData?video_appid=3000010&vplatform=2&vversion_name=8.2.96`, {
            method:"POST", headers:{"Content-Type":"application/json"}, data:JSON.stringify(epiBody), postType:"json"
        });
        const jsonDetail = safeJson(rawDetail);
        const jsonEpi = safeJson(rawEpi);
        const mainItem = safeGet(jsonDetail, "data", "module_list_datas", 0, "module_datas",0,"item_data_lists","item_datas",0,"item_params") || {};
        const starList = safeGet(jsonDetail, "data", "module_list_datas",0,"module_datas",0,"item_data_lists","item_datas",0,"sub_items","star_list","item_datas") || [];
        const actors = starList.map(x=>safeGet(x,"item_params","name")).filter(Boolean);
        const epiItems = safeGet(jsonEpi, "data", "module_list_datas",-1,"module_datas",-1,"item_data_lists","item_datas") || [];
        const playList = [];
        for(const ep of epiItems){
            const p = safeGet(ep,"item_params") || {};
            const epTitle = p.union_title || "";
            const vid = p.item_id;
            if(!vid) continue;
            playList.push(`${epTitle}$${cid}@${vid}`);
        }
        const vod = {
            vod_id: cid,
            vod_name: mainItem.title || "",
            vod_pic: fixPicUrl(mainItem.new_pic_hz || ""),
            vod_year: String(mainItem.year || ""),
            vod_area: mainItem.area_name || "",
            vod_actor: actors.join(","),
            vod_director: "",
            vod_remarks: mainItem.holly_online_time || mainItem.hotval || "",
            vod_content: mainItem.cover_description || "",
            vod_play_from: "腾讯视频",
            vod_play_url: playList.join("#")
        };
        return JSON.stringify({ list:[vod] });
    } catch(e) {
        console.error("detail error",e.message);
        return JSON.stringify({ list:[] });
    }
}

async function search(wd, quick, pg) {
    pg = Number(pg) || 1;
    try {
        const body = {
            "version": "24072901",
            "clientType":1,
            "filterValue":"",
            "uuid": uuidv4(),
            "retry":0,
            "query": wd,
            "pagenum": pg-1,
            "pagesize":30,
            "queryFrom":0,
            "searchDatakey":"",
            "transInfo":"",
            "isneedQc":true,
            "preQid":"",
            "adClientInfo":"",
            "extraInfo":{"isNewMarkLabel":"1","multi_terminal_pc":"1"}
        };
        const raw = await request(`${API_HOST}/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2`,{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            data:JSON.stringify(body),
            postType:"json"
        });
        const json = safeJson(raw);
        const boxList = safeGet(json,"data","areaBoxList") || [];
        const list = [];
        for(const box of boxList){
            const itemList = safeGet(box,"itemList") || [];
            for(const it of itemList){
                const doc = safeGet(it,"doc") || {};
                const cid = doc.id;
                if(!cid) continue;
                const videoInfo = safeGet(it,"videoInfo") || {};
                const tagRaw = videoInfo.imgTag || "{}";
                const tag = safeJson(tagRaw) || {};
                list.push({
                    vod_id: String(cid),
                    vod_name: videoInfo.title || "",
                    vod_pic: fixPicUrl(videoInfo.imgUrl || ""),
                    vod_year: safeGet(tag,"tag_2","text") || "",
                    vod_remarks: safeGet(tag,"tag_4","text") || ""
                });
            }
        }
        return JSON.stringify({
            list,
            page:pg,
            pagecount: pg+1
        });
    } catch(e) {
        console.error("search error",e.message);
        return JSON.stringify({ list:[], page:pg, pagecount:0 });
    }
}

async function play(flag, id, flags) {
    try {
        const parts = id.split("@");
        const cid = parts[0];
        const vid = parts[1] || "";
        const realPlayUrl = `${HOST}/x/cover/${cid}/${vid}.html`;
        // 原简易js规则依赖本地代理解析，cat环境没有本地代理，这里返回嗅探模式
        return JSON.stringify({
            parse:1,
            url: realPlayUrl,
            header:{
                "User-Agent":UA,
                "Referer":HOST+"/"
            }
        });
    } catch(e) {
        console.error("play error",e.message);
        return JSON.stringify({ parse:1, url:"", header:{"User-Agent":UA} });
    }
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, search, play };
}
//（注：内容由AI生成）
