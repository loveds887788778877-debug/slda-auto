"""
슬다 자동화 v12.0 - Railway 24시간 완전판
- ffmpeg 자동 설치 (Railway 서버)
- Gemini AI 매일 다른 제목+대본 (무료!)
- Pexels 실시간 영상 자동 다운로드
- 아침(09:00) / 점심(13:00) / 저녁(19:00) 자동 업로드
- 15채널 × 3회 = 하루 45개 완전 자동!
- PC 없어도 24시간 가동!
"""

import os, time, threading, subprocess, pickle, schedule, random, json, re, requests
from pathlib import Path
from datetime import datetime
from gtts import gTTS
from flask import Flask, jsonify, render_template_string, request as flask_request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

BASE_DIR   = Path(os.environ.get("BASE_DIR", "/app"))
OUTPUT_DIR = BASE_DIR / "output"
TOKENS_DIR = BASE_DIR / "tokens"
FFMPEG_EXE = "ffmpeg"

OUTPUT_DIR.mkdir(exist_ok=True)
TOKENS_DIR.mkdir(exist_ok=True)

GEMINI_KEYS = json.loads(os.environ.get("GEMINI_API_KEYS", "[]"))
PEXELS_KEY  = os.environ.get("PEXELS_API_KEY", "")

CHANNELS = {
    "ch01": {"name": "한줄의 린",   "category": "명언",    "tone": "감성적이고 따뜻한",     "pexels": "motivation sunrise nature"},
    "ch02": {"name": "무드웨이브",  "category": "노래",    "tone": "감성적이고 음악적인",    "pexels": "music piano aesthetic cafe"},
    "ch03": {"name": "피트노트",    "category": "운동",    "tone": "활기차고 동기부여되는",  "pexels": "workout fitness gym"},
    "ch04": {"name": "딥슬립룸",    "category": "ASMR",   "tone": "조용하고 편안한",        "pexels": "rain forest nature sleep"},
    "ch05": {"name": "몽글클럽",    "category": "반려동물","tone": "귀엽고 따뜻한",          "pexels": "cute puppy kitten cat"},
    "ch06": {"name": "픽앤리뷰",    "category": "리뷰",    "tone": "솔직하고 유익한",        "pexels": "product review lifestyle"},
    "ch07": {"name": "이슈타르",    "category": "이슈",    "tone": "흥미롭고 자극적인",      "pexels": "city people urban crowd"},
    "ch08": {"name": "뷰티끄",      "category": "뷰티",    "tone": "세련되고 트렌디한",      "pexels": "beauty makeup skincare"},
    "ch09": {"name": "한끼스케치",  "category": "음식",    "tone": "맛있고 식욕자극하는",    "pexels": "korean food cooking"},
    "ch10": {"name": "무비착",      "category": "영화",    "tone": "흥미롭고 분석적인",      "pexels": "cinema film dramatic"},
    "ch11": {"name": "룩북노트",    "category": "패션",    "tone": "세련되고 트렌디한",      "pexels": "fashion style outfit"},
    "ch12": {"name": "드라마찜",    "category": "드라마",  "tone": "감동적이고 공감가는",    "pexels": "couple romantic drama"},
    "ch13": {"name": "트래블로그",  "category": "여행",    "tone": "설레고 신나는",          "pexels": "travel landscape beautiful"},
    "ch14": {"name": "퀴즈는",      "category": "퀴즈",    "tone": "재미있고 도전적인",      "pexels": "quiz thinking brain"},
    "ch15": {"name": "밈스토리",    "category": "밈",      "tone": "유머러스하고 공감가는",  "pexels": "funny comedy laugh"},
}

TITLE_HOOKS = {
    "명언": ["이 말 한마디가 내 인생을 바꿨다", "오늘 꼭 봐야 할 명언", "모르면 손해인 인생 명언"],
    "노래": ["지금 당장 듣고 싶은 노래", "감성 터지는 플레이리스트", "이 노래 모르면 아쉬울걸요"],
    "운동": ["이것만 해도 살 빠진다", "하루 5분으로 몸이 달라진다", "이 운동 안하면 후회한다"],
    "ASMR": ["잠 못 드는 밤에 틀어봐", "이거 들으면 5분 안에 잠든다", "마음이 편해지는 소리"],
    "반려동물": ["이 영상 보면 힐링된다", "너무 귀여워서 심장 터질뻔", "보는 순간 미소짓게 되는"],
    "리뷰": ["이거 살까 말까 고민된다면", "솔직하게 말해드릴게요", "구매 전 꼭 봐야 할 영상"],
    "이슈": ["이거 실화냐", "지금 난리난 이슈", "이 사실 몰랐죠"],
    "뷰티": ["이 방법 왜 이제 알았을까", "피부 좋아지는 꿀팁", "10분만에 달라지는 방법"],
    "음식": ["이거 안먹어봤으면 손해", "이 맛 알면 못 끊는다", "오늘 뭐 먹을지 고민된다면"],
    "영화": ["이 영화 안봤으면 지금 당장", "결말이 충격적인 영화", "인생 영화 추가됩니다"],
    "패션": ["이 코디 진짜 예쁘다", "오늘 뭐 입을지 고민된다면", "패피들이 즐겨 입는"],
    "드라마": ["이 장면에서 다 울었다", "이 드라마 안보면 후회", "OST 들으면 그 장면이"],
    "여행": ["여기 진짜 가보고 싶다", "가면 반드시 후회없는 곳", "여행 계획 있다면 꼭 봐"],
    "퀴즈": ["이거 맞추면 천재", "100명 중 5명만 맞춘다", "자신있으면 도전해봐"],
    "밈": ["이거 보고 웃으면 정상", "공감 100% 상황", "현실 공감 터지는 순간"],
}

TOPICS = {
    "명언": ["성공", "도전", "희망", "용기", "행복", "사랑", "성장", "꿈", "감사", "극복"],
    "노래": ["발라드", "팝", "힙합", "R&B", "인디", "OST"],
    "운동": ["스쿼트", "플랭크", "유산소", "근력", "홈트", "다이어트", "복근"],
    "ASMR": ["빗소리", "파도소리", "모닥불", "숲속", "카페소음", "수면"],
    "반려동물": ["강아지", "고양이", "산책", "목욕", "훈련", "간식"],
    "리뷰": ["맛집", "제품", "앱", "서비스", "가성비템"],
    "이슈": ["연예", "사회", "경제", "스포츠", "해외토픽"],
    "뷰티": ["스킨케어", "메이크업", "헤어", "네일", "선크림"],
    "음식": ["한식", "디저트", "야식", "건강식", "간식", "레시피"],
    "영화": ["액션", "로맨스", "공포", "코미디", "SF", "감동"],
    "패션": ["캐주얼", "데이트룩", "오피스룩", "미니멀", "트렌드"],
    "드라마": ["로맨스", "스릴러", "코미디", "사극", "의학"],
    "여행": ["제주도", "부산", "서울", "경주", "일본", "유럽"],
    "퀴즈": ["역사", "과학", "지리", "연예인", "음식", "상식"],
    "밈": ["공감짤", "직장인", "학생", "연인", "현실공감"],
}

upload_log = []
upload_stats = {"success": 0, "fail": 0, "running": False}
pipeline_status = {}

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info":"ℹ️","ok":"✅","err":"❌","warn":"⚠️"}.get(level,"•")
    entry = f"[{ts}] {icon} {msg}"
    upload_log.append({"time":ts,"level":level,"msg":msg,"full":entry})
    if len(upload_log) > 300: upload_log.pop(0)
    print(entry)

def install_ffmpeg():
    try:
        subprocess.run(["ffmpeg","-version"],capture_output=True,check=True)
        log("ffmpeg 준비됨!", "ok")
    except:
        log("ffmpeg 설치 중...", "info")
        os.system("apt-get update -qq && apt-get install -y ffmpeg -qq")
        log("ffmpeg 설치 완료!", "ok")

def generate_content(ch_id):
    ch = CHANNELS[ch_id]
    category = ch["category"]
    random_topic = random.choice(TOPICS.get(category, ["꿀팁"]))
    hook = random.choice(TITLE_HOOKS.get(category, ["꼭 봐야 할"]))
    try:
        if not GEMINI_KEYS: raise Exception("키 없음")
        gemini_key = random.choice(GEMINI_KEYS)
        prompt = f"""한국 유튜브 쇼츠 크리에이터로서 JSON만 출력하세요.
채널:{ch['name']} 주제:{random_topic} 톤:{ch['tone']} 힌트:{hook}
{{"title":"이모지+후킹문구 25자이내","script":"20초분량 자연스럽게","tags":"{category},{random_topic},쇼츠","description":"채널설명"}}"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        res = requests.post(url,json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.9,"maxOutputTokens":500}},timeout=30)
        result = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = result.replace("```json","").replace("```","").strip()
        parsed = json.loads(result)
        log(f"[{ch['name']}] Gemini 제목: {parsed.get('title','')}", "ok")
        return parsed
    except Exception as e:
        log(f"[{ch['name']}] Gemini 오류:{e} → 기본값", "warn")
        return {"title":f"✨ {hook} {random_topic}","script":f"안녕하세요! {ch['name']}입니다! 오늘은 {random_topic} 꿀팁! 구독 좋아요 부탁드려요!","tags":f"{category},{random_topic},쇼츠","description":f"{ch['name']} | {random_topic}"}

def get_pexels_video(ch_id):
    ch = CHANNELS[ch_id]
    if not PEXELS_KEY: return None
    try:
        headers = {"Authorization": PEXELS_KEY}
        res = requests.get("https://api.pexels.com/videos/search",headers=headers,params={"query":ch["pexels"],"per_page":15,"page":random.randint(1,8),"orientation":"portrait"},timeout=30)
        videos = res.json().get("videos",[])
        if not videos: return None
        video = random.choice(videos)
        vf = sorted([f for f in video["video_files"]],key=lambda x:x.get("height",0),reverse=True)
        video_path = OUTPUT_DIR / f"{ch_id}_pexels.mp4"
        r = requests.get(vf[0]["link"],stream=True,timeout=90)
        with open(video_path,"wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        log(f"[{ch['name']}] Pexels 완료!", "ok")
        return video_path
    except Exception as e:
        log(f"[{ch['name']}] Pexels 오류:{e}", "warn")
        return None

def make_voice(script, ch_id):
    audio_path = OUTPUT_DIR / f"{ch_id}_voice.mp3"
    try:
        gTTS(text=script,lang="ko",slow=False).save(str(audio_path))
        return audio_path
    except: return None

def make_subtitle(script, ch_id):
    srt_path = OUTPUT_DIR / f"{ch_id}.srt"
    sentences = [s.strip() for s in re.split(r"[.!?]",script) if len(s.strip())>1] or [script]
    srt = ""; start = 0.0
    for i,s in enumerate(sentences,1):
        end = start + max(2.0,len(s)*0.13)
        def fmt(t):
            h,r=divmod(int(t),3600); m,sec=divmod(r,60); ms=int((t-int(t))*1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        srt += f"{i}\n{fmt(start)} --> {fmt(end)}\n{s}\n\n"
        start = end + 0.3
    with open(srt_path,"w",encoding="utf-8") as f: f.write(srt)
    return srt_path

def make_video(ch_id, base_video, audio_path, subtitle_path):
    output_path = OUTPUT_DIR / f"{ch_id}_final.mp4"
    base_vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    sub_filter = ""
    if subtitle_path and Path(subtitle_path).exists():
        sub_str = str(subtitle_path).replace("\\","/")
        sub_filter = f",subtitles='{sub_str}':force_style='FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,Alignment=2,MarginV=80'"
    cmd = [FFMPEG_EXE,"-y","-i",str(base_video),"-i",str(audio_path),"-c:v","libx264","-preset","fast","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-shortest","-vf",base_vf+sub_filter,str(output_path)]
    try:
        result = subprocess.run(cmd,capture_output=True,timeout=180)
        if result.returncode != 0 or not output_path.exists():
            cmd2 = [FFMPEG_EXE,"-y","-i",str(base_video),"-i",str(audio_path),"-c:v","libx264","-preset","fast","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-shortest","-vf",base_vf,str(output_path)]
            subprocess.run(cmd2,capture_output=True,timeout=180)
        if output_path.exists():
            log(f"[{ch_id}] 영상 합성 완료!", "ok")
            return output_path
        return None
    except Exception as e:
        log(f"[{ch_id}] 영상 오류:{e}", "err")
        return None

def get_youtube_service(ch_id):
    for name in [f"ch{ch_id[2:]}_token.pickle",f"token_{ch_id}.pickle"]:
        p = TOKENS_DIR / name
        if p.exists():
            try:
                with open(p,"rb") as f: creds = pickle.load(f)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(p,"wb") as f: pickle.dump(creds,f)
                return build("youtube","v3",credentials=creds)
            except: pass
    log(f"[{ch_id}] 토큰 없음!", "err")
    return None

def upload_youtube(ch_id, video_path, content):
    ch = CHANNELS[ch_id]
    youtube = get_youtube_service(ch_id)
    if not youtube: return False
    try:
        tags = [t.strip() for t in content.get("tags","").split(",")][:15]
        body = {"snippet":{"title":content.get("title",f"{ch['name']} 쇼츠"),"description":content.get("description",""),"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
        media = MediaFileUpload(str(video_path),mimetype="video/mp4",resumable=True)
        req = youtube.videos().insert(part="snippet,status",body=body,media_body=media)
        response = None
        while response is None: _,response = req.next_chunk()
        vid_id = response.get("id","")
        log(f"[{ch['name']}] ✅ 업로드 완료! https://youtube.com/shorts/{vid_id}", "ok")
        pipeline_status[ch_id] = "완료"
        return True
    except Exception as e:
        log(f"[{ch['name']}] 업로드 오류:{str(e)[:200]}", "err")
        pipeline_status[ch_id] = "실패"
        return False

def run_pipeline(channel_ids, script=None):
    upload_stats["running"] = True
    results = {"success":[],"fail":[]}
    for i,ch_id in enumerate(channel_ids,1):
        if ch_id not in CHANNELS: continue
        ch = CHANNELS[ch_id]
        pipeline_status[ch_id] = "진행중"
        log(f"━━ [{i}/{len(channel_ids)}] {ch['name']} 시작 ━━", "info")
        try:
            content = generate_content(ch_id)
            use_script = script if script else content.get("script","")
            base_video = get_pexels_video(ch_id)
            if not base_video:
                existing = [f for f in OUTPUT_DIR.glob(f"{ch_id}*.mp4") if "final" not in f.name]
                base_video = existing[0] if existing else None
            if not base_video:
                log(f"[{ch['name']}] 영상 없음!", "err")
                results["fail"].append(ch["name"]); pipeline_status[ch_id]="실패"; continue
            audio = make_voice(use_script, ch_id)
            if not audio:
                results["fail"].append(ch["name"]); pipeline_status[ch_id]="실패"; continue
            subtitle = make_subtitle(use_script, ch_id)
            video = make_video(ch_id, base_video, audio, subtitle)
            if not video:
                results["fail"].append(ch["name"]); pipeline_status[ch_id]="실패"; continue
            ok = upload_youtube(ch_id, video, content)
            (results["success"] if ok else results["fail"]).append(ch["name"])
            time.sleep(random.randint(10,20))
        except Exception as e:
            log(f"[{ch['name']}] 오류:{e}", "err")
            results["fail"].append(ch["name"]); pipeline_status[ch_id]="실패"
    upload_stats["success"] += len(results["success"])
    upload_stats["fail"] += len(results["fail"])
    upload_stats["running"] = False
    log(f"🎉 완료! 성공:{len(results['success'])}개 실패:{len(results['fail'])}개", "ok")

ALL_CHANNELS = list(CHANNELS.keys())

def auto_round(round_name):
    if upload_stats["running"]: return
    log(f"🕐 [{round_name}] 자동 시작! 15채널", "ok")
    threading.Thread(target=run_pipeline,args=(ALL_CHANNELS,""),daemon=True).start()

def setup_schedule():
    schedule.every().day.at("09:00").do(auto_round,"🌅 아침")
    schedule.every().day.at("13:00").do(auto_round,"☀️ 점심")
    schedule.every().day.at("19:00").do(auto_round,"🌙 저녁")
    def run_loop():
        while True: schedule.run_pending(); time.sleep(30)
    threading.Thread(target=run_loop,daemon=True).start()
    log("⏰ 🌅09:00 ☀️13:00 🌙19:00 자동 설정!", "ok")

def get_token_status():
    return {ch_id: (TOKENS_DIR/f"ch{ch_id[2:]}_token.pickle").exists() or (TOKENS_DIR/f"token_{ch_id}.pickle").exists() for ch_id in CHANNELS}

app = Flask(__name__)

HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>슬다 v12</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#0b0f19;color:#f1f5f9;padding:14px;max-width:480px;margin:0 auto}h1{font-size:20px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:2px}.sub{color:#475569;font-size:10px;margin-bottom:10px}.sched{background:#1e293b;border-radius:10px;padding:10px;margin-bottom:12px;font-size:12px;text-align:center;color:#94a3b8}.sched span{color:#4ade80;font-weight:700}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:12px}.stat{background:#1e293b;border-radius:10px;padding:10px;text-align:center}.stat-n{font-size:22px;font-weight:800;color:#4ade80}.stat-n.e{color:#f87171}.stat-n.r{color:#fbbf24}.stat-l{font-size:9px;color:#64748b;margin-top:2px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:10px}.card{background:#1e293b;border:1.5px solid #334155;border-radius:10px;padding:8px 4px;cursor:pointer;text-align:center}.card.sel{border-color:#3b82f6;background:#1e3a5f}.card.auth{border-left:3px solid #4ade80}.card.noauth{border-left:3px solid #f87171}.card.done{border-color:#4ade80!important;background:#052e16!important}.card.fail{border-color:#f87171!important;background:#2d0707!important}.card.running{border-color:#fbbf24!important}.cn{font-size:10px;font-weight:700}.cc{font-size:8px;color:#64748b}.br{display:flex;gap:7px;margin-bottom:10px}button{padding:10px 12px;border-radius:10px;border:none;cursor:pointer;font-size:12px;font-weight:700}.bb{background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;flex:1;padding:15px;font-size:15px;border-radius:12px;width:100%;margin-bottom:10px}.bb:disabled{background:#334155;color:#64748b}.bg{background:#1e293b;color:#94a3b8;border:1px solid #334155}.lb{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px;height:200px;overflow-y:auto;font-family:monospace;font-size:10px;line-height:1.6}.lo{color:#4ade80}.le{color:#f87171}.lw{color:#fbbf24}.li{color:#64748b}.lbl{font-size:10px;color:#475569;margin-bottom:6px;font-weight:700}</style></head><body><h1>⚡ 슬다 자동화 v12</h1><p class="sub">Gemini AI 무료 · Pexels 실시간 · PC없이 24시간!</p><div class="sched">자동: <span>🌅09:00</span> · <span>☀️13:00</span> · <span>🌙19:00</span> · 하루 45개!</div><div class="stats"><div class="stat"><div class="stat-n" id="ss">0</div><div class="stat-l">성공</div></div><div class="stat"><div class="stat-n e" id="sf">0</div><div class="stat-l">실패</div></div><div class="stat"><div class="stat-n r" id="sr">대기</div><div class="stat-l">상태</div></div></div><div class="lbl">채널 선택</div><div class="grid" id="cg"></div><div class="br"><button class="bg" onclick="sa()" style="flex:1">전체선택</button><button class="bg" onclick="ca()" style="flex:1">전체해제</button></div><button class="bb" id="sb" onclick="go()">🚀 지금 바로 업로드!</button><div class="br"><button class="bg" onclick="document.getElementById('lb').innerHTML=''" style="width:100%">로그 초기화</button></div><div class="lbl">실행 로그</div><div class="lb" id="lb"><div class="li">대기 중...</div></div><script>const CH={{channels|tojson}};let sel=new Set(),tok={};function rg(){document.getElementById('cg').innerHTML=Object.entries(CH).map(([id,ch])=>`<div class="card ${tok[id]?'auth':'noauth'}" id="c${id}" onclick="tg('${id}')"><div class="cn">${ch.name}</div><div class="cc">${ch.category}</div></div>`).join('');}function tg(id){const el=document.getElementById('c'+id);sel.has(id)?(sel.delete(id),el.classList.remove('sel')):(sel.add(id),el.classList.add('sel'));}function sa(){Object.keys(CH).forEach(id=>{sel.add(id);document.getElementById('c'+id)?.classList.add('sel');});}function ca(){sel.forEach(id=>document.getElementById('c'+id)?.classList.remove('sel'));sel.clear();}function go(){if(!sel.size){alert('채널 선택!');return;}document.getElementById('sb').disabled=true;document.getElementById('sb').textContent='⏳ 업로드 중...';fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channels:[...sel]})}).then(r=>r.json());}function pl(){fetch('/logs').then(r=>r.json()).then(d=>{const b=document.getElementById('lb');b.innerHTML=d.logs.map(l=>`<div class="l${l.level[0]}">${l.full}</div>`).join('')||'<div class="li">없음</div>';b.scrollTop=b.scrollHeight;document.getElementById('ss').textContent=d.stats.success;document.getElementById('sf').textContent=d.stats.fail;const r=document.getElementById('sr');r.textContent=d.stats.running?'실행중':'대기';r.style.color=d.stats.running?'#fbbf24':'#94a3b8';if(!d.stats.running){document.getElementById('sb').disabled=false;document.getElementById('sb').textContent='🚀 지금 바로 업로드!';}Object.entries(d.pipeline||{}).forEach(([id,st])=>{const c=document.getElementById('c'+id);if(!c)return;c.classList.remove('done','fail','running');if(st==='완료')c.classList.add('done');else if(st==='실패')c.classList.add('fail');else if(st==='진행중')c.classList.add('running');});});}function cs(){fetch('/status').then(r=>r.json()).then(s=>{tok=s.tokens;rg();});}rg();cs();setInterval(pl,2000);setInterval(cs,15000);</script></body></html>"""

@app.route("/")
def dashboard(): return render_template_string(HTML,channels=CHANNELS)

@app.route("/status")
def status(): return jsonify({"tokens":get_token_status()})

@app.route("/run",methods=["POST"])
def run():
    if upload_stats["running"]: return jsonify({"status":"busy","msg":"이미 실행중!"})
    data = flask_request.json
    threading.Thread(target=run_pipeline,args=(data.get("channels",[]),data.get("script","")),daemon=True).start()
    return jsonify({"status":"ok","msg":f"🚀 {len(data.get('channels',[]))}개 시작!"})

@app.route("/logs")
def get_logs(): return jsonify({"logs":upload_log[-100:],"stats":upload_stats,"pipeline":pipeline_status})

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    log("슬다 자동화 v12.0 시작 🚀","ok")
    install_ffmpeg()
    setup_schedule()
    app.run(host="0.0.0.0",port=port,debug=False)
ENDOFFILE
