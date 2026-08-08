"""
슬다 자동화 v10 - Railway 24시간 완전판
"""

import os, time, threading, pickle
from pathlib import Path
from datetime import datetime
from gtts import gTTS
from flask import Flask, jsonify, render_template_string, request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ─── 경로 설정 (Railway/로컬 자동 감지) ──────────────────────
IS_RAILWAY  = os.environ.get("RAILWAY_ENVIRONMENT") is not None
BASE_DIR    = Path("/app") if IS_RAILWAY else Path(r"C:\Users\MYCOM\Desktop\제코자동화")
OUTPUT_DIR  = Path("/tmp/output") if IS_RAILWAY else BASE_DIR / "output"
TOKENS_DIR  = Path("/app/tokens") if IS_RAILWAY else BASE_DIR / "tokens"
FFMPEG_EXE  = "ffmpeg" if IS_RAILWAY else str(BASE_DIR / "bin" / "ffmpeg.exe")
BASE_VIDEO  = BASE_DIR / "base_video.mp4"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 채널 설정 ───────────────────────────────────────────────
CHANNELS = {
    "ch01": {"name": "한줄의 린",   "category": "명언"},
    "ch02": {"name": "무드웨이브",  "category": "노래"},
    "ch03": {"name": "피트노트",    "category": "운동"},
    "ch04": {"name": "딥슬립룸",    "category": "ASMR"},
    "ch05": {"name": "몽글클럽",    "category": "반려동물"},
    "ch06": {"name": "픽앤리뷰",    "category": "리뷰"},
    "ch07": {"name": "이슈타르",    "category": "이슈"},
    "ch08": {"name": "뷰티끄",      "category": "뷰티"},
    "ch09": {"name": "한끼스케치",  "category": "음식"},
    "ch10": {"name": "무비착",      "category": "영화"},
    "ch11": {"name": "룩북노트",    "category": "패션"},
    "ch12": {"name": "드라마찜",    "category": "드라마"},
    "ch13": {"name": "트래블로그",  "category": "여행"},
    "ch14": {"name": "퀴즈는",      "category": "퀴즈"},
    "ch15": {"name": "밈스토리",    "category": "밈"},
}

upload_log = []
upload_stats = {"success": 0, "fail": 0, "running": False}

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info":"ℹ️","ok":"✅","err":"❌","warn":"⚠️"}.get(level,"•")
    entry = f"[{ts}] {icon} {msg}"
    upload_log.append({"time":ts,"level":level,"msg":msg,"full":entry})
    if len(upload_log) > 200:
        upload_log.pop(0)
    print(entry)

def get_youtube_service(ch_id):
    token_path = TOKENS_DIR / f"token_{ch_id}.pickle"
    if not token_path.exists():
        log(f"[{ch_id}] 토큰 없음!", "err")
        return None
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        log(f"[{ch_id}] 인증 오류: {e}", "err")
        return None

def make_voice(script, ch_id):
    audio_path = OUTPUT_DIR / f"{ch_id}_voice.mp3"
    try:
        gTTS(text=script, lang="ko").save(str(audio_path))
        log(f"[{ch_id}] 음성 생성 완료", "ok")
        return audio_path
    except Exception as e:
        log(f"[{ch_id}] 음성 오류: {e}", "err")
        return None

def make_video(ch_id, audio_path):
    if not BASE_VIDEO.exists():
        log(f"base_video.mp4 없음!", "err")
        return None
    import subprocess
    output_path = OUTPUT_DIR / f"{ch_id}_final.mp4"
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", str(BASE_VIDEO),
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0 or not output_path.exists():
        log(f"[{ch_id}] 영상 합성 실패", "warn")
        return None
    log(f"[{ch_id}] 영상 합성 완료", "ok")
    return output_path

def upload_to_youtube(ch_id, video_path):
    ch = CHANNELS[ch_id]
    youtube = get_youtube_service(ch_id)
    if not youtube:
        return False
    title = f"[{ch['name']}] {datetime.now().strftime('%m월 %d일')} 쇼츠"
    body = {
        "snippet": {
            "title": title,
            "description": f"#{ch['category']} #슬다 #쇼츠",
            "tags": [ch["category"], "쇼츠", "슬다"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    try:
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        log(f"[{ch['name']}] 업로드 중...", "info")
        while response is None:
            _, response = req.next_chunk()
        log(f"[{ch['name']}] 업로드 완료! 🎉", "ok")
        return True
    except Exception as e:
        log(f"[{ch['name']}] 업로드 오류: {str(e)[:200]}", "err")
        return False

def run_pipeline(channel_ids, script=None):
    upload_stats["running"] = True
    default_script = script or "안녕하세요! 슬다가 오늘의 꿀팁을 알려드려요!"
    results = {"success": [], "fail": []}
    for ch_id in channel_ids:
        if ch_id not in CHANNELS:
            continue
        ch_name = CHANNELS[ch_id]["name"]
        try:
            audio = make_voice(default_script, ch_id)
            if not audio:
                results["fail"].append(ch_name); continue
            video = make_video(ch_id, audio)
            if not video:
                results["fail"].append(ch_name); continue
            ok = upload_to_youtube(ch_id, video)
            (results["success"] if ok else results["fail"]).append(ch_name)
            time.sleep(3)
        except Exception as e:
            log(f"[{ch_name}] 오류: {e}", "err")
            results["fail"].append(ch_name)
    upload_stats["success"] += len(results["success"])
    upload_stats["fail"]    += len(results["fail"])
    upload_stats["running"]  = False
    log(f"🎉 완료 → 성공:{len(results['success'])}개 실패:{len(results['fail'])}개", "ok")

def get_token_status():
    return {ch_id: (TOKENS_DIR / f"token_{ch_id}.pickle").exists() for ch_id in CHANNELS}

app = Flask(__name__)

HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>슬다 자동화 v10</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#0b0f19;color:#f1f5f9;padding:16px;max-width:480px;margin:0 auto}h1{font-size:20px;font-weight:700;margin-bottom:2px}.sub{color:#64748b;font-size:11px;margin-bottom:14px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}.stat{background:#1e293b;border-radius:10px;padding:10px;text-align:center}.stat-n{font-size:22px;font-weight:700;color:#4ade80}.stat-n.err{color:#f87171}.stat-n.run{color:#fbbf24}.stat-l{font-size:10px;color:#64748b;margin-top:2px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:12px}.card{background:#1e293b;border:1.5px solid #334155;border-radius:10px;padding:9px;cursor:pointer;transition:all .15s}.card.sel{border-color:#3b82f6;background:#1e3a5f}.card.auth{border-left:3px solid #4ade80}.card.noauth{border-left:3px solid #f87171}.cn{font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cc{font-size:10px;color:#64748b;margin-top:2px}.br{display:flex;gap:8px;margin-bottom:12px}button{padding:10px 14px;border-radius:10px;border:none;cursor:pointer;font-size:12px;font-weight:600}.bb{background:#3b82f6;color:#fff;flex:1;padding:14px;font-size:15px;border-radius:12px;width:100%;margin-bottom:10px}.bb:disabled{background:#334155;color:#64748b;cursor:not-allowed}.bg{background:#334155;color:#cbd5e1}textarea{width:100%;background:#1e293b;border:1.5px solid #334155;border-radius:10px;color:#f1f5f9;padding:11px;font-size:13px;resize:vertical;min-height:65px;margin-bottom:12px}.lb{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:11px;height:220px;overflow-y:auto;font-family:monospace;font-size:11px;line-height:1.6}.lo{color:#4ade80}.le{color:#f87171}.lw{color:#fbbf24}.li{color:#94a3b8}.lbl{font-size:11px;color:#94a3b8;margin-bottom:7px;font-weight:600}</style></head><body><h1>⚡ 슬다 자동화 v10</h1><p class="sub">YouTube API · Railway 24시간 · 15채널</p><div class="stats"><div class="stat"><div class="stat-n" id="statSuccess">0</div><div class="stat-l">성공</div></div><div class="stat"><div class="stat-n err" id="statFail">0</div><div class="stat-l">실패</div></div><div class="stat"><div class="stat-n run" id="statRun">대기</div><div class="stat-l">상태</div></div></div><div class="lbl">채널 선택 <span id="selCount" style="color:#3b82f6"></span></div><div class="grid" id="channelGrid"></div><div class="br"><button class="bg" onclick="selectAll()">전체선택</button><button class="bg" onclick="clearAll()">전체해제</button><button class="bg" onclick="selectAuth()">인증채널만</button></div><div class="lbl">대본</div><textarea id="scriptText" placeholder="안녕하세요! 슬다입니다 🎉"></textarea><button class="bb" id="startBtn" onclick="startUpload()">🚀 업로드 시작</button><div class="br"><button class="bg" onclick="clearLog()" style="width:100%">로그 초기화</button></div><div class="lbl">실행 로그</div><div class="lb" id="logBox"><div class="li">대기 중...</div></div><script>const channels={{channels|tojson}};let sel=new Set(),tokenStatus={};function renderGrid(){document.getElementById('channelGrid').innerHTML=Object.entries(channels).map(([id,ch])=>{const auth=tokenStatus[id];return`<div class="card ${auth?'auth':'noauth'}" id="c${id}" onclick="tog('${id}')"><div class="cn">${ch.name}</div><div class="cc">${ch.category}${auth?' 🔑':''}</div></div>`;}).join('');}function tog(id){const el=document.getElementById('c'+id);if(sel.has(id)){sel.delete(id);el.classList.remove('sel');}else{sel.add(id);el.classList.add('sel');}document.getElementById('selCount').textContent=sel.size>0?`(${sel.size}개 선택)`:'';}function selectAll(){Object.keys(channels).forEach(id=>{sel.add(id);const el=document.getElementById('c'+id);if(el)el.classList.add('sel');});document.getElementById('selCount').textContent=`(${sel.size}개 선택)`;}function clearAll(){sel.forEach(id=>{const el=document.getElementById('c'+id);if(el)el.classList.remove('sel');});sel.clear();document.getElementById('selCount').textContent='';}function selectAuth(){clearAll();Object.keys(channels).forEach(id=>{if(tokenStatus[id]){sel.add(id);const el=document.getElementById('c'+id);if(el)el.classList.add('sel');}});document.getElementById('selCount').textContent=`(${sel.size}개 선택)`;}function startUpload(){if(sel.size===0){alert('채널을 먼저 선택하세요!');return;}const btn=document.getElementById('startBtn');btn.disabled=true;btn.textContent='⏳ 업로드 중...';fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channels:[...sel],script:document.getElementById('scriptText').value})}).then(r=>r.json()).then(d=>{});}function clearLog(){document.getElementById('logBox').innerHTML='';}function pollLog(){fetch('/logs').then(r=>r.json()).then(data=>{const b=document.getElementById('logBox');b.innerHTML=data.logs.map(l=>`<div class="l${l.level[0]}">${l.full}</div>`).join('')||'<div class="li">로그 없음</div>';b.scrollTop=b.scrollHeight;const s=data.stats;document.getElementById('statSuccess').textContent=s.success;document.getElementById('statFail').textContent=s.fail;const runEl=document.getElementById('statRun');runEl.textContent=s.running?'실행중':'대기';runEl.style.color=s.running?'#fbbf24':'#94a3b8';const btn=document.getElementById('startBtn');if(!s.running){btn.disabled=false;btn.textContent='🚀 업로드 시작';}});}function checkStatus(){fetch('/status').then(r=>r.json()).then(s=>{tokenStatus=s.tokens;renderGrid();});}renderGrid();checkStatus();setInterval(pollLog,2000);setInterval(checkStatus,15000);</script></body></html>"""

@app.route("/")
def dashboard():
    return render_template_string(HTML, channels=CHANNELS)

@app.route("/status")
def status():
    return jsonify({"tokens": get_token_status()})

@app.route("/run", methods=["POST"])
def run():
    if upload_stats["running"]:
        return jsonify({"status": "busy", "msg": "이미 업로드 중!"})
    data = request.json
    threading.Thread(target=run_pipeline, args=(data.get("channels",[]), data.get("script","")), daemon=True).start()
    return jsonify({"status": "ok", "msg": f"🚀 {len(data.get('channels',[]))}개 채널 시작!"})

@app.route("/logs")
def get_logs():
    return jsonify({"logs": upload_log[-100:], "stats": upload_stats})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log("슬다 자동화 v10 시작 🚀", "ok")
    app.run(host="0.0.0.0", port=port, debug=False)
