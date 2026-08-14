"""
슬다 자동화 v15.0 - Gemini 환경변수 수정 + make_rich_background Railway 호환 + 검은화면 방지
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

# ✅ 수정1: 단일 키도 받고, 배열도 받도록
_raw_keys = os.environ.get("GEMINI_API_KEYS", "[]")
try:
    GEMINI_KEYS = json.loads(_raw_keys)
    if isinstance(GEMINI_KEYS, str):
        GEMINI_KEYS = [GEMINI_KEYS]
except:
    GEMINI_KEYS = []

# 단일 키 환경변수도 지원
_single_key = os.environ.get("GEMINI_API_KEY", "")
if _single_key and _single_key not in GEMINI_KEYS:
    GEMINI_KEYS.append(_single_key)

# AIzaSy 키만 필터링 (AQ. 형식의 aistudio 키도 허용)
GEMINI_KEYS = [k for k in GEMINI_KEYS if k.startswith("AIzaSy") or k.startswith("AQ.")]

PEXELS_KEY  = os.environ.get("PEXELS_API_KEY", "")
KLING_KEY   = os.environ.get("KLING_API_KEY", "")
SLDA_IMAGE_URL = "https://raw.githubusercontent.com/Loveds8877887788877/SLDA-/main/slda.jpg"

COUPANG_LINK = "https://partners.coupang.com/"
TOSS_LINK = "https://sharelink.toss.im/links/best-ranking?signup=complete"
NAVER_LINK = "https://brandconnect.naver.com/979331624407424/affiliate/products-link?persist=true"

CHANNEL_LINKS = {
    "ch06": f"추천 제품: {COUPANG_LINK} 토스혜택: {TOSS_LINK} 네이버쇼핑: {NAVER_LINK}",
    "ch10": f"영화혜택: {TOSS_LINK} 추천상품: {COUPANG_LINK}",
    "ch15": f"오늘의추천: {COUPANG_LINK} 토스혜택: {TOSS_LINK}",
    "default": f"추천상품: {COUPANG_LINK} 토스혜택: {TOSS_LINK}",
}

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

# 채널별 배경 색상 테마
CHANNEL_COLORS = {
    "ch01": "0x2C1B4E",
    "ch02": "0x0D1B2A",
    "ch03": "0x1A3A1A",
    "ch04": "0x080820",
    "ch05": "0x2E1A0E",
    "ch06": "0x1A1A2E",
    "ch07": "0x0E1117",
    "ch08": "0x2C0A1E",
    "ch09": "0x1A0A00",
    "ch10": "0x0A0A1A",
    "ch11": "0x1A0D00",
    "ch12": "0x0A1628",
    "ch13": "0x0A1A0A",
    "ch14": "0x1A1A00",
    "ch15": "0x1A0A0A",
}

upload_log = []
upload_stats = {"success": 0, "fail": 0, "running": False}
pipeline_status = {}

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info":"i","ok":"OK","err":"ERR","warn":"WARN"}.get(level,"•")
    entry = f"[{ts}] {icon} {msg}"
    upload_log.append({"time":ts,"level":level,"msg":msg,"full":entry})
    if len(upload_log) > 300:
        upload_log.pop(0)
    print(entry)

def install_ffmpeg():
    try:
        subprocess.run(["ffmpeg","-version"], capture_output=True, check=True)
        log("ffmpeg 준비됨!", "ok")
    except:
        log("ffmpeg 설치 중...", "info")
        os.system("apt-get update -qq && apt-get install -y ffmpeg -qq")
        log("ffmpeg 설치 완료!", "ok")

def test_gemini_key(key):
    """Gemini 키 유효성 빠르게 테스트"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        res = requests.post(
            url,
            json={"contents":[{"parts":[{"text":"hi"}]}],"generationConfig":{"maxOutputTokens":10}},
            timeout=10
        )
        rj = res.json()
        if "candidates" in rj:
            return True
        err = rj.get("error",{})
        if err.get("status") in ["PERMISSION_DENIED","API_KEY_INVALID"]:
            return False
        return True  # 다른 오류는 일단 허용
    except:
        return True  # 네트워크 오류는 허용

def get_valid_gemini_keys():
    """시작시 유효한 키만 필터링"""
    valid = []
    for k in GEMINI_KEYS:
        if test_gemini_key(k):
            valid.append(k)
            log(f"Gemini 키 OK: ...{k[-6:]}", "ok")
        else:
            log(f"Gemini 키 차단됨 제거: ...{k[-6:]}", "warn")
    return valid if valid else GEMINI_KEYS  # 다 막히면 원본 사용

def generate_content(ch_id):
    ch = CHANNELS[ch_id]
    category = ch["category"]
    random_topic = random.choice(TOPICS.get(category, ["꿀팁"]))
    hook = random.choice(TITLE_HOOKS.get(category, ["꼭 봐야 할"]))
    try:
        if not GEMINI_KEYS:
            raise Exception("Gemini 키 없음")
        gemini_key = random.choice(GEMINI_KEYS)
        prompt = (
            "한국 유튜브 쇼츠 크리에이터로서 JSON만 출력하세요.\n"
            f"채널:{ch['name']} 주제:{random_topic} 톤:{ch['tone']} 힌트:{hook}\n"
            '{"title":"이모지+후킹문구 25자이내","script":"20초분량 자연스럽게",'
            f'"tags":"{category},{random_topic},쇼츠","description":"채널설명"}}'
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        res = requests.post(
            url,
            json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.9,"maxOutputTokens":500}},
            timeout=30
        )
        rjson = res.json()
        if "candidates" not in rjson or not rjson["candidates"]:
            raise Exception(f"응답없음:{rjson}")
        result = rjson["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = result.replace("```json","").replace("```","").strip()
        parsed = json.loads(result)
        log(f"[{ch['name']}] Gemini 성공: {parsed.get('title','')}", "ok")
        return parsed
    except Exception as e:
        log(f"[{ch['name']}] Gemini 오류:{e} → 기본값사용", "warn")
        return {
            "title": f"{hook} {random_topic}",
            "script": f"안녕하세요! {ch['name']}입니다! 오늘은 {random_topic} 꿀팁을 알려드릴게요! 구독과 좋아요 부탁드려요!",
            "tags": f"{category},{random_topic},쇼츠",
            "description": f"{ch['name']} | {random_topic}"
        }

def get_kling_video(ch_id, script):
    if not KLING_KEY:
        return None
    if ch_id not in ["ch06", "ch10", "ch15"]:
        return None
    try:
        log(f"[{ch_id}] Kling AI 영상 생성 시작...", "info")
        headers = {
            "Authorization": f"Bearer {KLING_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model_name": "kling-v1",
            "image_url": SLDA_IMAGE_URL,
            "prompt": "A Korean woman talking naturally to camera, vertical video",
            "duration": "5",
            "aspect_ratio": "9:16",
            "mode": "std"
        }
        res = requests.post(
            "https://api.klingai.com/v1/videos/image2video",
            headers=headers,
            json=data,
            timeout=30
        )
        if res.status_code != 200:
            log(f"[{ch_id}] Kling API 오류:{res.status_code} {res.text[:100]}", "warn")
            return None
        task_id = res.json().get("data", {}).get("task_id")
        if not task_id:
            log(f"[{ch_id}] Kling task_id 없음", "warn")
            return None
        log(f"[{ch_id}] Kling 작업중 task:{task_id}", "info")
        for i in range(18):
            time.sleep(10)
            check = requests.get(
                f"https://api.klingai.com/v1/videos/image2video/{task_id}",
                headers=headers,
                timeout=15
            )
            if check.status_code != 200:
                continue
            status = check.json().get("data", {}).get("task_status")
            if status == "succeed":
                video_url = check.json()["data"]["task_result"]["videos"][0]["url"]
                kling_path = OUTPUT_DIR / f"{ch_id}_kling.mp4"
                r = requests.get(video_url, stream=True, timeout=60)
                with open(kling_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                if kling_path.exists() and kling_path.stat().st_size > 50000:
                    log(f"[{ch_id}] Kling 완료! ({kling_path.stat().st_size//1024}KB)", "ok")
                    return kling_path
            elif status == "failed":
                log(f"[{ch_id}] Kling 실패", "warn")
                return None
            log(f"[{ch_id}] Kling 대기... {(i+1)*10}초", "info")
        log(f"[{ch_id}] Kling 타임아웃", "warn")
        return None
    except Exception as e:
        log(f"[{ch_id}] Kling 오류:{e}", "warn")
        return None

def get_pexels_video(ch_id):
    ch = CHANNELS[ch_id]
    if not PEXELS_KEY:
        log(f"[{ch['name']}] Pexels 키 없음", "warn")
        return None
    try:
        headers = {"Authorization": PEXELS_KEY}
        query = ch["pexels"]
        log(f"[{ch['name']}] Pexels 검색: {query}", "info")
        res = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": 15, "page": random.randint(1,3), "orientation": "portrait"},
            timeout=30
        )
        if res.status_code != 200:
            log(f"[{ch['name']}] Pexels HTTP오류:{res.status_code}", "warn")
            return None
        videos = res.json().get("videos", [])
        log(f"[{ch['name']}] Pexels 결과:{len(videos)}개", "info")
        if not videos:
            return None
        video = random.choice(videos)
        vfiles = sorted(
            [f for f in video.get("video_files", []) if f.get("height",0) >= 480],
            key=lambda x: x.get("height",0), reverse=True
        )
        if not vfiles:
            log(f"[{ch['name']}] Pexels 파일없음", "warn")
            return None
        link = vfiles[0]["link"]
        log(f"[{ch['name']}] Pexels 다운로드 시작 ({vfiles[0].get('height')}p)", "info")
        raw_path = OUTPUT_DIR / f"{ch_id}_raw.mp4"
        r = requests.get(link, stream=True, timeout=120)
        with open(raw_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        size = raw_path.stat().st_size
        log(f"[{ch['name']}] Pexels 다운로드:{size//1024}KB", "info")
        if size < 10000:
            log(f"[{ch['name']}] Pexels 파일 너무 작음", "warn")
            return None
        conv_path = OUTPUT_DIR / f"{ch_id}_conv.mp4"

        # 1차: 가로→세로 패딩 방식 (선 없음, 블러 배경)
        conv_cmd1 = [
            FFMPEG_EXE, "-y",
            "-i", str(raw_path),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-vf", (
                "split[original][copy];"
                "[copy]scale=1080:1920,gblur=sigma=30[blurred];"
                "[original]scale=1080:1920:force_original_aspect_ratio=decrease[scaled];"
                "[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
            ),
            "-r", "30", "-t", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(conv_path)
        ]
        r1 = subprocess.run(conv_cmd1, capture_output=True, timeout=180)
        if r1.returncode == 0 and conv_path.exists() and conv_path.stat().st_size > 50000:
            log(f"[{ch['name']}] Pexels 블러배경 완료! ({conv_path.stat().st_size//1024}KB)", "ok")
            return conv_path

        # 2차: 단순 크롭 방식
        log(f"[{ch['name']}] Pexels 1차 실패 → 2차(크롭) 시도", "warn")
        conv_cmd2 = [
            FFMPEG_EXE, "-y",
            "-i", str(raw_path),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-r", "30", "-t", "30",
            "-movflags", "+faststart",
            str(conv_path)
        ]
        r2 = subprocess.run(conv_cmd2, capture_output=True, timeout=180)
        if r2.returncode == 0 and conv_path.exists() and conv_path.stat().st_size > 50000:
            log(f"[{ch['name']}] Pexels 크롭 완료! ({conv_path.stat().st_size//1024}KB)", "ok")
            return conv_path

        # 3차: 최소 변환
        log(f"[{ch['name']}] Pexels 2차 실패 → 3차(단순) 시도", "warn")
        conv_cmd3 = [
            FFMPEG_EXE, "-y",
            "-i", str(raw_path),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:-2",
            "-r", "30", "-t", "30",
            "-movflags", "+faststart",
            str(conv_path)
        ]
        r3 = subprocess.run(conv_cmd3, capture_output=True, timeout=180)
        if r3.returncode == 0 and conv_path.exists() and conv_path.stat().st_size > 50000:
            log(f"[{ch['name']}] Pexels 단순변환 완료! ({conv_path.stat().st_size//1024}KB)", "ok")
            return conv_path

        # 4차: raw 직접 사용
        log(f"[{ch['name']}] Pexels 변환 모두 실패 → raw 사용", "warn")
        if raw_path.exists() and raw_path.stat().st_size > 100000:
            log(f"[{ch['name']}] Pexels raw 직접 사용 ({raw_path.stat().st_size//1024}KB)", "ok")
            return raw_path

        log(f"[{ch['name']}] Pexels 완전 실패", "warn")
        return None
    except Exception as e:
        log(f"[{ch['name']}] Pexels 오류:{e}", "warn")
        return None

# ✅ 수정2: make_rich_background - Railway 완전 호환 (3단계 폴백)
def make_rich_background(ch_id, duration=30):
    """
    Railway ffmpeg 완전 호환 버전
    단계1: 단색(drawbox 없음) → 단계2: lavfi color → 단계3: 최소 배경
    """
    output_path = OUTPUT_DIR / f"{ch_id}_bg.mp4"
    color = CHANNEL_COLORS.get(ch_id, "0x1a1a2e")

    # ── 단계1: 가장 단순한 단색 배경 (drawbox 없음) ──
    cmd1 = [
        FFMPEG_EXE, "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:size=1080x1920:rate=30",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    try:
        r = subprocess.run(cmd1, capture_output=True, timeout=60)
        if r.returncode == 0 and output_path.exists() and output_path.stat().st_size > 10000:
            log(f"[{ch_id}] 배경(단색) 생성 완료 ({output_path.stat().st_size//1024}KB)", "ok")
            return output_path
        log(f"[{ch_id}] 단계1 실패 → 단계2 시도", "warn")
    except Exception as e:
        log(f"[{ch_id}] 단계1 예외:{e}", "warn")

    # ── 단계2: testsrc2 (ffmpeg 내장 테스트 패턴) ──
    try:
        cmd2 = [
            FFMPEG_EXE, "-y",
            "-f", "lavfi",
            "-i", f"testsrc2=size=1080x1920:rate=30",
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        r2 = subprocess.run(cmd2, capture_output=True, timeout=60)
        if r2.returncode == 0 and output_path.exists() and output_path.stat().st_size > 10000:
            log(f"[{ch_id}] 배경(testsrc2) 생성 완료", "ok")
            return output_path
        log(f"[{ch_id}] 단계2 실패 → 단계3 시도", "warn")
    except Exception as e:
        log(f"[{ch_id}] 단계2 예외:{e}", "warn")

    # ── 단계3: smptebars (가장 기본적인 ffmpeg 소스) ──
    try:
        cmd3 = [
            FFMPEG_EXE, "-y",
            "-f", "lavfi",
            "-i", "smptebars=size=1080x1920:rate=30",
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        r3 = subprocess.run(cmd3, capture_output=True, timeout=60)
        if r3.returncode == 0 and output_path.exists() and output_path.stat().st_size > 10000:
            log(f"[{ch_id}] 배경(smptebars) 생성 완료", "ok")
            return output_path
    except Exception as e:
        log(f"[{ch_id}] 단계3 예외:{e}", "warn")

    log(f"[{ch_id}] 모든 배경 생성 실패", "err")
    return None

# ✅ 수정3: 업로드 전 영상 유효성 검사
def check_video_valid(video_path):
    """검은화면/빈파일 업로드 완전 차단"""
    if not video_path:
        return False, "경로없음"
    p = Path(video_path)
    if not p.exists():
        return False, "파일없음"
    size = p.stat().st_size
    if size < 50000:
        return False, f"크기부족:{size}B (최소50KB)"
    # ffprobe로 영상 스트림 확인
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0",
             str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        out = probe.stdout.strip()
        if probe.returncode == 0 and out and "," in out:
            w, h = out.split(",")[:2]
            if int(w) > 0 and int(h) > 0:
                return True, f"{w}x{h}"
        return False, f"스트림없음(probe:{out})"
    except Exception as e:
        # ffprobe 없으면 크기로만 판단
        if size > 50000:
            return True, f"크기OK:{size//1024}KB"
        return False, f"검증실패:{e}"

ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # 기본: Rachel

def make_voice(script, ch_id):
    audio_path = OUTPUT_DIR / f"{ch_id}_voice.mp3"

    # 1순위: ElevenLabs (자연스러운 음성)
    if ELEVENLABS_KEY:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": ELEVENLABS_KEY,
                "Content-Type": "application/json"
            }
            data = {
                "text": script,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.3,
                    "use_speaker_boost": True
                }
            }
            res = requests.post(url, headers=headers, json=data, timeout=30)
            if res.status_code == 200:
                with open(audio_path, "wb") as f:
                    f.write(res.content)
                if audio_path.stat().st_size > 1000:
                    log(f"[{ch_id}] ElevenLabs 음성 완료! ({audio_path.stat().st_size//1024}KB)", "ok")
                    return audio_path
            else:
                log(f"[{ch_id}] ElevenLabs 오류:{res.status_code} → gTTS 폴백", "warn")
        except Exception as e:
            log(f"[{ch_id}] ElevenLabs 예외:{e} → gTTS 폴백", "warn")

    # 2순위: gTTS (무료 폴백)
    try:
        log(f"[{ch_id}] gTTS 음성 생성 중...", "info")
        gTTS(text=script, lang="ko", slow=False).save(str(audio_path))
        if audio_path.stat().st_size < 1000:
            log(f"[{ch_id}] gTTS 파일 너무 작음", "err")
            return None
        log(f"[{ch_id}] gTTS 음성 완료! ({audio_path.stat().st_size//1024}KB)", "ok")
        return audio_path
    except Exception as e:
        log(f"[{ch_id}] 음성 완전 실패:{e}", "err")
        return None

def make_video(ch_id, base_video, audio_path):
    output_path = OUTPUT_DIR / f"{ch_id}_final.mp4"
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", str(base_video),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path)
    ]
    try:
        log(f"[{ch_id}] 합성 중...", "info")
        subprocess.run(cmd, capture_output=True, timeout=120)
        if output_path.exists() and output_path.stat().st_size > 50000:
            log(f"[{ch_id}] 합성 완료! ({output_path.stat().st_size//1024}KB)", "ok")
            return output_path
        # 재인코딩 시도
        cmd2 = [
            FFMPEG_EXE, "-y",
            "-i", str(base_video),
            "-i", str(audio_path),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(output_path)
        ]
        subprocess.run(cmd2, capture_output=True, timeout=180)
        if output_path.exists() and output_path.stat().st_size > 50000:
            log(f"[{ch_id}] 재인코딩 완료!", "ok")
            return output_path
        log(f"[{ch_id}] 합성 실패", "err")
        return None
    except subprocess.TimeoutExpired:
        log(f"[{ch_id}] 합성 타임아웃", "err")
        return None
    except Exception as e:
        log(f"[{ch_id}] 합성 오류:{e}", "err")
        return None

def get_youtube_service(ch_id):
    ch_num = ch_id[2:]
    candidates = [
        TOKENS_DIR / f"ch{ch_num}_token.pickle",
        TOKENS_DIR / f"token_{ch_id}.pickle",
        TOKENS_DIR / f"{ch_id}_token.pickle",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "rb") as f:
                    creds = pickle.load(f)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(p, "wb") as f:
                        pickle.dump(creds, f)
                return build("youtube", "v3", credentials=creds)
            except Exception as e:
                log(f"[{ch_id}] 토큰 오류({p.name}):{e}", "warn")
    log(f"[{ch_id}] 토큰 없음!", "err")
    return None

def upload_youtube(ch_id, video_path, content):
    # ✅ 업로드 전 검증 (검은화면 차단)
    valid, info = check_video_valid(video_path)
    if not valid:
        log(f"[{ch_id}] 업로드 차단: {info}", "err")
        return False

    ch = CHANNELS[ch_id]
    youtube = get_youtube_service(ch_id)
    if not youtube:
        return False
    try:
        tags = [t.strip() for t in content.get("tags","").split(",")][:15]
        body = {
            "snippet": {
                "title": content.get("title", f"{ch['name']} 쇼츠")[:100],
                "description": content.get("description", ""),
                "tags": tags,
                "categoryId": "22"
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = req.next_chunk()
        vid_id = response.get("id", "")
        log(f"[{ch['name']}] ✅ 업로드 완료! https://youtube.com/shorts/{vid_id}", "ok")
        pipeline_status[ch_id] = "완료"
        return True
    except Exception as e:
        log(f"[{ch['name']}] 업로드 오류:{str(e)[:200]}", "err")
        pipeline_status[ch_id] = "실패"
        return False

def run_pipeline(channel_ids, script=None):
    upload_stats["running"] = True
    results = {"success": [], "fail": []}
    for i, ch_id in enumerate(channel_ids, 1):
        if ch_id not in CHANNELS:
            continue
        ch = CHANNELS[ch_id]
        pipeline_status[ch_id] = "진행중"
        log(f"[{i}/{len(channel_ids)}] {ch['name']} 시작", "info")
        try:
            content = generate_content(ch_id)
            use_script = script if script else content.get("script", "")

            # 링크 자동 삽입
            link = CHANNEL_LINKS.get(ch_id, CHANNEL_LINKS["default"])
            content["description"] = content.get("description", "") + "\n\n" + link + "\n\n#shorts #쇼츠"

            # Kling AI → Pexels → 배경 순서
            base_video = get_kling_video(ch_id, use_script)
            if not base_video:
                base_video = get_pexels_video(ch_id)
            if not base_video:
                log(f"[{ch['name']}] Pexels 없음 → 배경 생성", "warn")
                base_video = make_rich_background(ch_id, duration=30)

            if not base_video:
                log(f"[{ch['name']}] 영상 생성 완전 실패 → 스킵", "err")
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            audio = make_voice(use_script, ch_id)
            if not audio:
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            video = make_video(ch_id, base_video, audio)
            if not video:
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            ok = upload_youtube(ch_id, video, content)
            if ok:
                results["success"].append(ch["name"])
            else:
                results["fail"].append(ch["name"])

            time.sleep(random.randint(10, 20))
        except Exception as e:
            log(f"[{ch['name']}] 오류:{e}", "err")
            results["fail"].append(ch["name"])
            pipeline_status[ch_id] = "실패"

    upload_stats["success"] += len(results["success"])
    upload_stats["fail"] += len(results["fail"])
    upload_stats["running"] = False
    log(f"완료! 성공:{len(results['success'])}개 실패:{len(results['fail'])}개", "ok")

# 자동 돌릴 12개 (무비착/픽앤리뷰/밈스토리 제외)
AUTO_CHANNELS = [
    "ch01",  # 한줄의 린 (명언)
    "ch02",  # 무드웨이브 (노래)
    "ch03",  # 피트노트 (운동)
    "ch04",  # 딥슬립룸 (ASMR)
    "ch05",  # 몽글클럽 (반려동물)
    "ch07",  # 이슈타르 (이슈)
    "ch08",  # 뷰티끄 (뷰티)
    "ch09",  # 한끼스케치 (음식)
    "ch11",  # 룩북노트 (패션)
    "ch12",  # 드라마찜 (드라마)
    "ch13",  # 트래블로그 (여행)
    "ch14",  # 퀴즈는 (퀴즈)
]

# 잠시 중단 채널 3개
PAUSED_CHANNELS = ["ch06", "ch10", "ch15"]  # 픽앤리뷰, 무비착, 밈스토리

ALL_CHANNELS = list(CHANNELS.keys())

def auto_round(round_name):
    if upload_stats["running"]:
        return
    log(f"{round_name} 자동 시작! (12채널 - 픽앤리뷰/무비착/밈 제외)", "ok")
    threading.Thread(target=run_pipeline, args=(AUTO_CHANNELS, ""), daemon=True).start()

def setup_schedule():
    schedule.every().day.at("09:00").do(auto_round, "아침")
    schedule.every().day.at("13:00").do(auto_round, "점심")
    schedule.every().day.at("19:00").do(auto_round, "저녁")

    def run_loop():
        while True:
            schedule.run_pending()
            time.sleep(30)
    threading.Thread(target=run_loop, daemon=True).start()
    log("자동 12채널: 09:00 13:00 19:00 / 픽앤리뷰·무비착·밈 잠시 중단!", "ok")

def get_token_status():
    result = {}
    for ch_id in CHANNELS:
        ch_num = ch_id[2:]
        result[ch_id] = any([
            (TOKENS_DIR / f"ch{ch_num}_token.pickle").exists(),
            (TOKENS_DIR / f"token_{ch_id}.pickle").exists(),
            (TOKENS_DIR / f"{ch_id}_token.pickle").exists(),
        ])
    return result

app = Flask(__name__)

HTML = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>슬다 v15.0</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#0b0f19;color:#f1f5f9;padding:14px;max-width:480px;margin:0 auto}h1{font-size:20px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:2px}.sub{color:#475569;font-size:10px;margin-bottom:10px}.sched{background:#1e293b;border-radius:10px;padding:10px;margin-bottom:12px;font-size:12px;text-align:center;color:#94a3b8}.sched span{color:#4ade80;font-weight:700}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:12px}.stat{background:#1e293b;border-radius:10px;padding:10px;text-align:center}.stat-n{font-size:22px;font-weight:800;color:#4ade80}.stat-n.e{color:#f87171}.stat-n.r{color:#fbbf24}.stat-l{font-size:9px;color:#64748b;margin-top:2px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:10px}.card{background:#1e293b;border:1.5px solid #334155;border-radius:10px;padding:8px 4px;cursor:pointer;text-align:center}.card.sel{border-color:#3b82f6;background:#1e3a5f}.card.auth{border-left:3px solid #4ade80}.card.noauth{border-left:3px solid #f87171}.card.done{border-color:#4ade80!important;background:#052e16!important}.card.fail{border-color:#f87171!important;background:#2d0707!important}.card.running{border-color:#fbbf24!important}.cn{font-size:10px;font-weight:700}.cc{font-size:8px;color:#64748b}.br{display:flex;gap:7px;margin-bottom:10px}button{padding:10px 12px;border-radius:10px;border:none;cursor:pointer;font-size:12px;font-weight:700}.bb{background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;padding:15px;font-size:15px;border-radius:12px;width:100%;margin-bottom:10px}.bb:disabled{background:#334155;color:#64748b}.bg{background:#1e293b;color:#94a3b8;border:1px solid #334155}.lb{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px;height:220px;overflow-y:auto;font-family:monospace;font-size:10px;line-height:1.6}.lo{color:#4ade80}.le{color:#f87171}.lw{color:#fbbf24}.li{color:#64748b}.lbl{font-size:10px;color:#475569;margin-bottom:6px;font-weight:700}.gemini-badge{background:#1e293b;border-radius:8px;padding:6px 10px;margin-bottom:10px;font-size:10px;color:#94a3b8;border:1px solid #334155}.gemini-badge span{color:#4ade80}</style></head><body><h1>슬다 자동화 v15.0</h1><p class="sub">Gemini 단일키 지원 · 배경 3단계 폴백 · 업로드 검증</p><div class="gemini-badge">Gemini: <span id="gk">확인중...</span> · Pexels: <span id="pk">확인중...</span> · 음성: <span id="ek">확인중...</span></div><div class="sched">자동 12채널: <span>09:00</span> · <span>13:00</span> · <span>19:00</span> (픽앤리뷰·무비착·밈 중단)</div><div class="stats"><div class="stat"><div class="stat-n" id="ss">0</div><div class="stat-l">성공</div></div><div class="stat"><div class="stat-n e" id="sf">0</div><div class="stat-l">실패</div></div><div class="stat"><div class="stat-n r" id="sr">대기</div><div class="stat-l">상태</div></div></div><div class="lbl">채널 선택</div><div class="grid" id="cg"></div><div class="br"><button class="bg" onclick="sa()" style="flex:1">전체선택</button><button class="bg" onclick="ca()" style="flex:1">전체해제</button></div><button class="bb" id="sb" onclick="go()">지금 바로 업로드!</button><div class="br"><button class="bg" onclick="document.getElementById('lb').innerHTML=''" style="width:100%">로그 초기화</button></div><div class="lbl">실행 로그</div><div class="lb" id="lb"><div class="li">대기 중...</div></div><script>const CH={{channels|tojson}};let sel=new Set(),tok={};function rg(){document.getElementById('cg').innerHTML=Object.entries(CH).map(([id,ch])=>`<div class="card ${tok[id]?'auth':'noauth'}" id="c${id}" onclick="tg('${id}')"><div class="cn">${ch.name}</div><div class="cc">${ch.category}</div></div>`).join('');}function tg(id){const el=document.getElementById('c'+id);sel.has(id)?(sel.delete(id),el.classList.remove('sel')):(sel.add(id),el.classList.add('sel'));}function sa(){Object.keys(CH).forEach(id=>{sel.add(id);document.getElementById('c'+id)?.classList.add('sel');});}function ca(){sel.forEach(id=>document.getElementById('c'+id)?.classList.remove('sel'));sel.clear();}function go(){if(!sel.size){alert('채널 선택!');return;}document.getElementById('sb').disabled=true;document.getElementById('sb').textContent='업로드 중...';fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channels:[...sel]})}).then(r=>r.json());}function pl(){fetch('/logs').then(r=>r.json()).then(d=>{const b=document.getElementById('lb');b.innerHTML=d.logs.map(l=>`<div class="l${l.level[0]}">${l.full}</div>`).join('')||'<div class="li">없음</div>';b.scrollTop=b.scrollHeight;document.getElementById('ss').textContent=d.stats.success;document.getElementById('sf').textContent=d.stats.fail;const r=document.getElementById('sr');r.textContent=d.stats.running?'실행중':'대기';r.style.color=d.stats.running?'#fbbf24':'#94a3b8';if(!d.stats.running){document.getElementById('sb').disabled=false;document.getElementById('sb').textContent='지금 바로 업로드!';}Object.entries(d.pipeline||{}).forEach(([id,st])=>{const c=document.getElementById('c'+id);if(!c)return;c.classList.remove('done','fail','running');if(st==='완료')c.classList.add('done');else if(st==='실패')c.classList.add('fail');else if(st==='진행중')c.classList.add('running');});});}function cs(){fetch('/status').then(r=>r.json()).then(s=>{tok=s.tokens;document.getElementById('gk').textContent=s.gemini_count+'개';document.getElementById('gk').style.color=s.gemini_count>0?'#4ade80':'#f87171';document.getElementById('pk').textContent=s.pexels?'연결됨':'없음';document.getElementById('pk').style.color=s.pexels?'#4ade80':'#f87171';document.getElementById('ek').textContent=s.elevenlabs?'ElevenLabs':'gTTS';document.getElementById('ek').style.color=s.elevenlabs?'#4ade80':'#fbbf24';rg();});}rg();cs();setInterval(pl,2000);setInterval(cs,15000);</script></body></html>"""

@app.route("/")
def dashboard():
    return render_template_string(HTML, channels=CHANNELS)

@app.route("/status")
def status():
    return jsonify({
        "tokens": get_token_status(),
        "gemini_count": len(GEMINI_KEYS),
        "pexels": bool(PEXELS_KEY),
        "elevenlabs": bool(ELEVENLABS_KEY)
    })

@app.route("/run", methods=["POST"])
def run():
    if upload_stats["running"]:
        return jsonify({"status": "busy", "msg": "이미 실행중!"})
    data = flask_request.json
    threading.Thread(target=run_pipeline, args=(data.get("channels",[]), data.get("script","")), daemon=True).start()
    return jsonify({"status": "ok", "msg": f"{len(data.get('channels',[]))}개 시작!"})

@app.route("/logs")
def get_logs():
    return jsonify({"logs": upload_log[-100:], "stats": upload_stats, "pipeline": pipeline_status})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log(f"슬다 자동화 v15.0 시작! Gemini키:{len(GEMINI_KEYS)}개 Pexels:{'OK' if PEXELS_KEY else '없음'}", "ok")
    install_ffmpeg()
    log("Gemini 키 검증 중...", "info")
    valid_keys = get_valid_gemini_keys()
    GEMINI_KEYS.clear()
    GEMINI_KEYS.extend(valid_keys)
    log(f"유효한 Gemini 키: {len(GEMINI_KEYS)}개", "ok")
    setup_schedule()
    app.run(host="0.0.0.0", port=port, debug=False)
