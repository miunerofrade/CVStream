import time
import re
import json
import shutil
from pathlib import Path
from ppt_extractor import PPTExtractor

def sanitize_filename(name):
    if not name: return ""
    cleaned = re.sub(r'[\\/*?:"<>|]', "-", str(name))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def format_ms_to_srt(ms: int) -> str:
    seconds = ms / 1000.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms_rem = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_rem:03d}"

def process_official_json(json_data: dict, task_dir: Path, task_name: str):
    txt_path = task_dir / f"{task_name}_transcript.txt" 
    data_dict = json_data.get("data")
    if not data_dict: raise ValueError("JSON 中未找到 'data' 字段")
    assembly_list = data_dict.get("afterAssemblyList", [])
    if not assembly_list: raise ValueError("字幕列表为空")
    full_text = [item.get("res", "").strip() for item in assembly_list if item.get("res", "").strip()]
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_text))
    return str(txt_path)

 
def fetch_dates_only(page):
    try:
        page.locator(".tecl-info").wait_for(state="visible", timeout=15000)
        js_parser = """
        () => {
            const items = Array.from(document.querySelectorAll('.list-item.student'));
            let playlist = [];
            items.forEach((el) => {
                const infoEl = el.querySelector('.bottom-left.sle');
                if (!infoEl) return;
                const match = infoEl.innerText.match(/(\\d{4}-\\d{2}-\\d{2})/);
                if (match) playlist.push({ date: match[1] });
            });
            return playlist; 
        }
        """
        page.locator(".list-item.student").first.wait_for(state="visible", timeout=15000)
        playlist = page.evaluate(js_parser)
        if not playlist: return []
         
        return sorted(list(set([item['date'] for item in playlist])), reverse=True)
    except Exception as e:
        return []

def execute_video_task(page, target_url, asr_worker, export_base_dir, stop_event, target_date=None, need_subtitle=True, need_ppt=False, keep_media=False):
    def get_time(): return time.strftime('%H:%M:%S')
    
    global_media_urls = {}
    captured_subtitles = {}
    active_lesson_seq = [-1] 

    def handle_response(response):
        if response.request.method == "OPTIONS" or not response.ok: return
        url = response.url
        if ".m3u8" in url or ".mp4" in url:
            base_url = url.split('?')[0]
            global_media_urls[base_url] = url
        if "/course/ai/translate/" in url:
            try:
                seq = active_lesson_seq[0]
                if seq != -1 and seq not in captured_subtitles:
                    captured_subtitles[seq] = response.json()
            except: pass

    page.on("response", handle_response)
    yield f"[{get_time()}] 正在扫描课程播放列表全局数据..."
    
    try:
        page.locator(".tecl-info").wait_for(state="visible", timeout=15000)
        raw_course_name = page.locator(".tecl-info .top").inner_text()
        course_name = sanitize_filename(raw_course_name)

        teacher_name = "未命名教师"
        try:
            teacher_locator = page.locator(".tecl-info .bottom .sle").first
            teacher_locator.wait_for(state="attached", timeout=5000) 
            raw_teacher = teacher_locator.get_attribute("title") or teacher_locator.inner_text()
            teacher_name = sanitize_filename(raw_teacher)
        except Exception:
            yield f"[{get_time()}] ⚠️ 老师信息提取失败，退回默认命名。"

        js_parser = """
        () => {
            const items = Array.from(document.querySelectorAll('.list-item.student'));
            let playlist = [];
            items.forEach((el, index) => {
                const infoEl = el.querySelector('.bottom-left.sle');
                const titleEl = el.querySelector('.title.sle');
                if (!infoEl) return;
                const rawInfo = infoEl.innerText;
                const match = rawInfo.match(/(\\d{4}-\\d{2}-\\d{2})\\s+(\\d{2}:\\d{2})/);
                const titleText = titleEl ? titleEl.innerText.trim() : "";
                let periodSeq = index + 1; 
                const seqMatch = titleText.match(/第(\\d+)节/);
                if (seqMatch) periodSeq = parseInt(seqMatch[1], 10);
                if (match) {
                    playlist.push({
                        index: index,              
                        date: match[1],            
                        time: match[2],            
                        title: titleText,
                        period_seq: periodSeq      
                    });
                }
            });
            return playlist; 
        }
        """
        
        page.locator(".list-item.student").first.wait_for(state="visible", timeout=15000)
        playlist = page.evaluate(js_parser)

        if not playlist: raise ValueError("无法解析播放列表时间数据。")

        all_dates = sorted(list(set([item['date'] for item in playlist])))

         
        if not target_date or target_date == "自动获取最新":
            target_date = all_dates[-1] 
            yield f"[{get_time()}] 未指定特定日期，系统自动锁定最新课程日: {target_date}"
        else:
            yield f"[{get_time()}] 校验用户指定抓取日期: {target_date}"
            if target_date not in all_dates:
                yield f"[{get_time()}] ❌ 严重错误: 当前课程不存在 [{target_date}] 的记录。"
                yield f"[{get_time()}] 🛑 拦截生效，已取消后续所有抓取动作以避免资源浪费。"
                return  

        target_items = [item for item in playlist if item['date'] == target_date]
        target_items.sort(key=lambda x: (x['time'], x['period_seq']))
        
        date_formatted = target_date.replace('-', '') 
        yield f"[{get_time()}] 课程 [{course_name}] | 主讲老师: {teacher_name}"
        yield f"[{get_time()}] {target_date} 共有 {len(target_items)} 节课，准备顺序执行..."

    except Exception as e:
        yield f"[{get_time()}] 播放列表初始化失败: {e}"
        return

    base_path = Path(export_base_dir)
     
    sub_dir = base_path / "subtitle" / course_name / f"{date_formatted}-{teacher_name}"
     
    media_dir = base_path / "media" / course_name / f"{date_formatted}-{teacher_name}"

     
    sub_dir.mkdir(parents=True, exist_ok=True)
    
    yield f"[{get_time()}] 产物分类目录已确认:"
    yield f"   - 字幕归档: {sub_dir}"
    if need_ppt or keep_media:
        media_dir.mkdir(parents=True, exist_ok=True)
        yield f"   - 媒体归档: {media_dir}"
    yield f"[{get_time()}] ----------------------------------------"
    
     
     
     
    yield f"[{get_time()}] [阶段 1/3] 启动高速网络侦听，搜集所有课时数据流..."
    
     
     
    try:
        yield f"[{get_time()}] [DEBUG] 执行状态重置，打破初始加载盲区..."
        first_title = page.locator(".list-item.student").first.locator(".title").first
        first_title.scroll_into_view_if_needed()
        first_title.click(timeout=3000)
        page.wait_for_timeout(2500)
    except Exception:
        pass

    for item in target_items:
        if stop_event.is_set():
            yield f"[{get_time()}] 🛑 接收到打断指令，停止执行后续任务..."
            asr_worker.abort()  
            return  
        
        seq = item['period_seq']
        active_lesson_seq[0] = seq
        
        try:
            yield f"[{get_time()}] 正在刺激第 {seq} 节节点响应..."
            pre_count = len(global_media_urls)
            
             
             
            container = page.locator(".list-item.student").nth(item['index'])
            click_target = container.locator(".title").first
            
            click_target.scroll_into_view_if_needed()
            page.wait_for_timeout(500)  
            
             
            for _ in range(2):
                click_target.hover()
                page.wait_for_timeout(200)
                click_target.click()  
                page.wait_for_timeout(3000)  
                
            post_count = len(global_media_urls)
            yield f"[{get_time()}] [DEBUG] 第 {seq} 节触发结束 | 拦截池流数量变化: {pre_count} -> {post_count}"
            
        except Exception as e:
            yield f"[{get_time()}] 第 {seq} 节节点触发异常: {e}"

    yield f"[{get_time()}] [阶段 2/3] 正在对捕获的无序数据流进行时间戳聚类与清洗..."
    clusters = {}
    
     
    for base_url, url in global_media_urls.items():
        filename = base_url.split('/')[-1]
        match_ts = re.search(r'^(\d{9})', filename)
        if match_ts:
            ts = int(match_ts.group(1))
            if ts not in clusters: clusters[ts] = []
            clusters[ts].append(url)
            yield f"[{get_time()}] [DEBUG] 成功归类: {filename} -> 簇 [{ts}]"
        else:
            yield f"[{get_time()}] [DEBUG] ⚠️ 无法提取时间戳的异形流: {filename}"
            
     
    sorted_ts_keys = sorted(clusters.keys())
    
    def calculate_url_weight(u):
        path = u.split('?')[0]
        parts = path.split('/')
        if len(parts) < 2: return 0
        dir_name = parts[-2]
        digits = re.findall(r'\d+', dir_name)
        return sum(int(d) for d in digits)

     
    for idx, item in enumerate(target_items):
        if idx < len(sorted_ts_keys):
            ts_key = sorted_ts_keys[idx]
            urls_in_cluster = clusters[ts_key]
            
             
            sorted_urls = sorted(urls_in_cluster, key=calculate_url_weight, reverse=True)
            item['final_url'] = sorted_urls[0]
            item['cluster_size'] = len(urls_in_cluster)
        else:
            item['final_url'] = None
            item['cluster_size'] = 0

    yield f"[{get_time()}] 聚类分析完成，共识别出 {len(sorted_ts_keys)} 组独立时间维度的有效流。"
    yield f"[{get_time()}] ----------------------------------------"


    if stop_event.is_set():
        yield f"[{get_time()}] 🛑 聚类完成但收到打断指令，取消后续处理。"
        return
     
     
     
    yield f"[{get_time()}] [阶段 3/3] 进入单线程持久化队列，执行本地 I/O 处理..."
    for item in target_items:
        task_name = f"{date_formatted}-{item['period_seq']}"
        
        yield f"\n[{get_time()}] 任务调度 -> 开始处理第 {item['period_seq']} 节 [{task_name}]..."

         
         
         
        expected_files = [
            sub_dir / f"{task_name}_transcript.txt",
            media_dir / f"{task_name}.mp4",
            media_dir / f"{task_name}.m4a",
            media_dir / f"{task_name}_PPT.pdf"
        ]
        
        if any(f.exists() for f in expected_files):
            yield f"[{get_time()}] 检测到部分产物已存在，执行增量跳过策略。"
             
            if (sub_dir / f"{task_name}_transcript.txt").exists():
                continue

         
        sub_json = captured_subtitles.get(item['period_seq'])
        got_official_sub = False
        
        if need_subtitle and sub_json:
            yield f"[{get_time()}] 🎯 挂载官方字幕数据，执行写入..."
            try:
                 
                process_official_json(sub_json, sub_dir, task_name)
                got_official_sub = True 
                yield f"[{get_time()}] ✅ 官方字幕写入成功。"
            except Exception as e:
                yield f"[{get_time()}] ❌ 官方字幕写入失败: {e}"

         
        final_url = item.get('final_url')
        need_media = need_ppt or keep_media or (need_subtitle and not got_official_sub)
        audio_only_mode = (not need_ppt) and (not keep_media) and (need_subtitle and not got_official_sub)

        if need_media:
            if final_url:
                msg = "轻量级提取 (仅音频)" if audio_only_mode else "全量抓取 (音视频)"
                yield f"[{get_time()}] 🚀 启动媒体处理引擎 {msg}..."
                
                try:
                     
                     
                    asr_worker.export_base_dir = sub_dir 
                    asr_worker.extract_media(final_url, target_url, audio_only=audio_only_mode)
                    
                    ext = ".m4a" if audio_only_mode else ".mp4"
                     
                    dest_media_path = media_dir / f"{task_name}{ext}"

                    if keep_media:
                        media_dir.mkdir(parents=True, exist_ok=True)  
                        if dest_media_path.exists(): dest_media_path.unlink()
                        shutil.copy2(asr_worker.temp_video_path, dest_media_path)

                    if need_subtitle and not got_official_sub:
                        yield f"[{get_time()}] 启动本地 ASR 音频转写..."
                        for progress_data in asr_worker.transcribe_and_export(task_name):
                            if "progress" in progress_data:
                                yield f"[ASR_PROGRESS] {json.dumps(progress_data)}"
                    
                    if need_ppt:
                        media_dir.mkdir(parents=True, exist_ok=True)
                        yield f"[{get_time()}] 🖼️ 初始化 PPT 视觉抽帧队列..."
                        try:
                            source_video_path = dest_media_path if dest_media_path.exists() else asr_worker.temp_video_path
                            ppt_worker = PPTExtractor(
                                video_path=str(source_video_path), 
                                output_dir=str(media_dir),  
                                task_name=task_name,
                                interval_sec=10,
                                diff_threshold=1.0 
                            )
                            yield from ppt_worker.extract_and_build_pdf(ignore_bottom_right_ratio=0.25)
                        except Exception as e:
                            yield f"[{get_time()}] ❌ PPT 提取级联崩溃: {e}"
                    
                    asr_worker._cleanup() 

                except Exception as e:
                    yield f"[{get_time()}] ❌ 媒体处理异常终止: {e}"

                if stop_event.is_set():
                    yield f"[{get_time()}] 🛑 任务打断，清理当前残骸..."
                    asr_worker.abort()
                    for f in expected_files:
                        if f.exists():
                            try: f.unlink()
                            except: pass
                    return
            else:
                yield f"[{get_time()}] ❌ 未检测到有效流，跳过媒体任务。"

        yield f"[{get_time()}] ----------------------------------------"

    yield f"\n[{get_time()}] 队列耗尽，所有阶段任务已安全完结。"