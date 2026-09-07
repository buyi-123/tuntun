# coding: utf-8
# ==================== 账号配置（请修改为你的账号密码） ====================
# 如果 guest/guest 无效，请在这里填入你的账号和密码
# 或者注册新账号后填入
LOGIN_USERNAME = "guest"
LOGIN_PASSWORD = "guest"
# ========================================================================
"""
站点信息:
- 主域名: https://www.asmr.one
- API域名: https://api.asmr-200.com
- 内容类型: ASMR 音声作品 (成人向)
- 数据来源: DLSite 同人音声
- 验证时间: 2026-09-07
- 备注: 该站提供免费在线收听，有R-18内容，通过API获取数据
- m3u8结构摘要: 音频分片为 .ts 格式，播放地址需从详情API获取
"""
import json
import re
import time
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        # __init__ 只做本地初始化，禁止网络请求
        self.host = "https://api.asmr-200.com"
        self.web_host = "https://www.asmr.one"
        self.classes = [
            {"type_id": "latest", "type_name": "最新收录"},
            {"type_id": "popular", "type_name": "热门作品"},
            {"type_id": "subtitle", "type_name": "带字幕"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.110 Mobile Safari/537.36",
            "Referer": self.web_host + "/",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.web_host,
        }
        # 搜索时需要使用的关键词
        self.search_keywords = ["asmr", "音声", "耳かき", "催眠", "彼女", "同人"]

    def getName(self):
        return "ASMR Online"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""
        # 自动登录获取 token
        self._login()

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 获取最新作品作为首页推荐
        try:
            resp = self.fetch(f"{self.host}/api/works?order=create_date&sort=desc&page=1&pageSize=20&subtitle=0", headers=self.headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                works = data.get("works", [])
                return {"list": self._parse_list(works)}
        except Exception as e:
            self.log(f"homeVideoContent error: {e}")
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        # tid 映射到不同的排序参数
        order = "create_date"
        sort = "desc"
        subtitle = 0
        if tid == "popular":
            order = "rank"
            sort = "asc"
        elif tid == "subtitle":
            subtitle = 1
        # 默认 "latest" 保持最新

        url = f"{self.host}/api/works?order={order}&sort={sort}&page={page}&pageSize=20&subtitle={subtitle}"
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                works = data.get("works", [])
                total = data.get("total", 0)
                pagecount = (total + 19) // 20 if total > 0 else 1
                return {
                    "list": self._parse_list(works),
                    "page": page,
                    "pagecount": pagecount,
                    "limit": 20,
                    "total": total
                }
        except Exception as e:
            self.log(f"categoryContent error: {e}")
        return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        work_id = ids[0] if ids else ""
        if not work_id:
            return {"list": []}
        try:
            # 获取作品详情
            resp = self.fetch(f"{self.host}/api/works/{work_id}", headers=self.headers, timeout=10)
            if resp and resp.status_code == 200:
                data = resp.json()
                work = data.get("work", {})
                if not work:
                    return {"list": []}

                # 尝试获取播放地址 (音频文件)
                play_url = ""
                try:
                    play_resp = self.fetch(f"{self.host}/api/works/{work_id}/play", headers=self.headers, timeout=10)
                    if play_resp and play_resp.status_code == 200:
                        play_data = play_resp.json()
                        play_url = play_data.get("play_url", "")
                except Exception as e:
                    self.log(f"detailContent 获取播放地址失败: {e}")

                # 构建详情数据
                vod = {
                    "vod_id": str(work_id),
                    "vod_name": work.get("title", ""),
                    "vod_pic": work.get("mainCoverUrl", ""),
                    "vod_remarks": f"评分: {work.get('rate_average_2dp', 0)} / 时长: {work.get('duration', 0)}秒",
                    "vod_actor": ", ".join([va.get("name", "") for va in work.get("vas", []) if va.get("name")]),
                    "vod_director": work.get("circle", {}).get("name", ""),
                    "vod_content": f"社团: {work.get('circle', {}).get('name', '')}\n"
                                  f"发布日期: {work.get('release', '')}\n"
                                  f"DLsite ID: {work.get('source_id', '')}\n"
                                  f"价格: {work.get('price', 0)} 日元",
                    "vod_play_from": "播放",
                    # 如果有播放地址则直接使用，否则使用作品ID让playerContent去获取
                    "vod_play_url": f"播放${play_url}" if play_url else f"播放${work_id}"
                }
                return {"list": [vod]}
        except Exception as e:
            self.log(f"detailContent error: {e}")
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        # 使用搜索API
        url = f"{self.host}/api/works?keyword={quote(key)}&page={page}&pageSize=20"
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                works = data.get("works", [])
                return {
                    "list": self._parse_list(works),
                    "page": page
                }
        except Exception as e:
            self.log(f"searchContent error: {e}")
        return {"list": [], "page": page}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        # 如果已经是完整播放地址，直接返回
        if id.startswith("http"):
            if ".m3u8" in id:
                return {"parse": 0, "url": self._m3u8_proxy_url(id), "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 0, "url": id, "header": {"User-Agent": self.headers["User-Agent"]}}

        # 尝试通过API获取播放地址（需要已登录）
        try:
            # 假设 id 是作品ID
            play_resp = self.fetch(f"{self.host}/api/works/{id}/play", headers=self.headers, timeout=10)
            if play_resp and play_resp.status_code == 200:
                play_data = play_resp.json()
                play_url = play_data.get("play_url", "")
                if play_url and play_url.startswith("http"):
                    if ".m3u8" in play_url:
                        return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {"User-Agent": self.headers["User-Agent"]}}
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"]}}
        except Exception as e:
            self.log(f"playerContent API获取失败: {e}")

        # 降级：让播放器去页面嗅探
        # 播放器会利用WebView中已登录的会话获取播放地址
        play_url = f"{self.web_host}/works/{id}"
        return {"parse": 1, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.web_host + "/"}}
    def _login(self):
        """自动登录获取 token"""
        try:
            login_url = f"{self.host}/api/auth/login"
            login_data = {"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD}
            resp = self.post(login_url, json=login_data, headers=self.headers, timeout=10)
            if resp and resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.headers["Authorization"] = f"Bearer {token}"
                    self.log("ASMR One 登录成功，token已获取")
                    return True
            # 尝试从响应头中获取 token
            if resp and resp.headers.get("Authorization"):
                self.headers["Authorization"] = resp.headers.get("Authorization")
                self.log("ASMR One 登录成功 (从响应头获取)")
                return True
            self.log("ASMR One 登录失败，将使用未登录状态")
            self.log(f"提示: 请检查账号密码是否正确，当前使用: {LOGIN_USERNAME}")
            return False
        except Exception as e:
            self.log(f"ASMR One 登录异常: {e}")
            return False

    def recommendContent(self, ids, pg):
        # 根据作品ID获取相关推荐 (这里简化，返回同社团作品)
        work_id = ids[0] if ids else ""
        if not work_id:
            return {"list": []}
        try:
            # 获取作品详情以获取circle_id
            resp = self.fetch(f"{self.host}/api/works/{work_id}", headers=self.headers)
            if resp and resp.status_code == 200:
                data = resp.json()
                work = data.get("work", {})
                circle_id = work.get("circle_id", 0)
                if circle_id:
                    # 获取同社团作品
                    circle_resp = self.fetch(f"{self.host}/api/works?circle_id={circle_id}&page=1&pageSize=20", headers=self.headers)
                    if circle_resp and circle_resp.status_code == 200:
                        circle_data = circle_resp.json()
                        works = circle_data.get("works", [])
                        # 过滤掉当前作品
                        works = [w for w in works if str(w.get("id")) != work_id]
                        return {"list": self._parse_list(works[:10])}
        except Exception as e:
            self.log(f"recommendContent error: {e}")
        return {"list": []}

    def destroy(self):
        pass

    def _parse_list(self, works):
        """解析作品列表，生成TVBox列表数据"""
        result = []
        for work in works:
            if not work or not work.get("id"):
                continue
            # 提取标签信息作为备注
            tags = work.get("tags", [])
            tag_names = [tag.get("name", "") for tag in tags if tag.get("name")]
            remark = f"⭐{work.get('rate_average_2dp', 0)}  {', '.join(tag_names[:3])}"
            if work.get("has_subtitle"):
                remark += "  [字幕]"
            # 处理多语言版本：如果有其他语言版本，在标题中标注
            title = work.get("title", "")
            lang_editions = work.get("language_editions", [])
            if lang_editions:
                langs = [ed.get("lang", "") for ed in lang_editions if ed.get("lang")]
                if langs:
                    title += f" ({','.join(langs)})"

            vod = {
                "vod_id": str(work.get("id")),
                "vod_name": title,
                "vod_pic": work.get("thumbnailCoverUrl") or work.get("mainCoverUrl") or "",
                "vod_remarks": remark,
                # 在vod_play_from中存储额外信息，用于detailContent
                "vod_play_from": f"circle_{work.get('circle_id', '')}",
            }
            # 将一些额外信息存储在vod_play_url中，以便在detailContent中获取
            # 这里不存储，detailContent会重新请求
            result.append(vod)
        return result

    def _m3u8_proxy_url(self, url):
        """生成m3u8代理地址"""
        return f"http://127.0.0.1:9978/proxy?do=py&url={quote(str(url or ''), safe='')}"

    def localProxy(self, param):
        """m3u8本地代理 + 广告分片过滤"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers["User-Agent"]}, timeout=15, verify=False)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8代理错误: " + str(e))
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """清洗m3u8：过滤广告分片，保留正片"""
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 多码率处理
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 单码率清洗
        source_path = urlparse(source_url).path
        source_parts = [p for p in source_path.split("/") if p]
        content_root = "/" + "/".join(source_parts[:2]) + "/" if len(source_parts) >= 2 else ""
        segments = []
        pending = []
        removed = 0

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                # 检查是否在正片目录下
                if content_root and content_root not in urlparse(media).path:
                    removed += 1
                else:
                    segments.extend(pending)
                    segments.append(media)
                pending = []
                continue
            segments.append(self._rewrite_m3u8_tag(line, source_url))

        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line == "#EXT-X-KEY:METHOD=NONE" or line == "#EXT-X-DISCONTINUITY":
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}")
        return "\n".join(out) + "\n"

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写m3u8标签中的URI，补全绝对地址"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                return f'URI="{urljoin(source_url, match.group(1))}"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line