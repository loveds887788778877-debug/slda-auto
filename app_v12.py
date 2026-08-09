"""
슬다 마스터 자동화 제어판 v11.0
- API 키 별도 config 파일로 분리 (보안 강화)
- 자막 완전 수정 (아래쪽, 굵게, 잘 보이게)
- 제목 후킹 문구로 자동 생성
- 채널별 맞춤 영상+대본
- 24시간 자동 재시작
"""

import os
import re
import time
import random
import threading
import subprocess
import requests
import pickle
import json
from pathlib import Path
from datetime import datetime
from gtts import gTTS

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from flask import Flask, jsonify, render_template_string, request as flask_request

BASE_DIR       = Path(r"C:\Users\MYCOM\Desktop\제코자동화")
VIDEO_POOL_DIR = Path(r"C:\Users\MYCOM\Desktop\제코자동화\base_video.mp4")
OUTPUT_DIR     = BASE_DIR / "output"
SUBTITLES_DIR  = BASE_DIR / "subtitles"
FFMPEG_EXE     = str(BASE_DIR / "bin" / "ffmpeg.exe")
SECRETS_DIR    = BASE_DIR / "client_secrets"
TOKENS_DIR     = BASE_DIR / "tokens"
CLIENT_SECRET  = str(SECRETS_DIR / "client_secrets.com.json")
CONFIG_FILE    = BASE_DIR / "config.json"  # API 키 별도 파일

OUTPUT_DIR.mkdir(exist_ok=True)
TOKENS_DIR.mkdir(exist_ok=True)
SUBTITLES_DIR.mkdir(exist_ok=True)

# ✅ config.json 파일에서 API 키 로드
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # 없으면 기본 파일 생성
    default = {
        "ANTHROPIC_API_KEY": "sk-ant-api03-d0hkSJwvkSveMeJTI6GLy-TvFEvzucIFyc3Nc_s_Q1t5RtDm11upTiQ--Y5YywAA",
        "PEXELS_API_KEY": "YfCfgmKWvpVdA9sPT4TikqIzuX24lhzRpb0ONRS06XNCu2eFCuYe30uR",
        "RUNWAY_API_KEY": "key_608db3846b68388fb446517bac79cc10038385faa384b53eb91c4658b80882f888dc439c66a4a1eacd2fd530df9acff3f4beae0f9adb8e0a48ad71abec77539b"
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(default, f, indent=2, ensure_ascii=False)
    print(f"✅ config.json 생성됨! {CONFIG_FILE} 파일에 API 키를 입력하세요!")
    return default

config = load_config()
ANTHROPIC_API_KEY = config.get("ANTHROPIC_API_KEY", "")
PEXELS_API_KEY    = config.get("PEXELS_API_KEY", "")
RUNWAY_API_KEY    = config.get("RUNWAY_API_KEY", "")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

YOUTUBE_CHANNELS = {
    "ch01": {"name": "한줄의 린",   "category": "명언",    "tone": "감성적이고 따뜻한",     "pexels_query": "motivation sunrise nature peaceful", "keyword": "명언,동기부여,힐링,자기계발,위로,성공명언,오늘의명언"},
    "ch02": {"name": "무드웨이브",  "category": "노래",    "tone": "감성적이고 음악적인",    "pexels_query": "music piano aesthetic cafe rain",    "keyword": "노래,음악,감성,플레이리스트,힐링음악,BGM,노래추천"},
    "ch03": {"name": "피트노트",    "category": "운동",    "tone": "활기차고 동기부여되는",  "pexels_query": "workout fitness gym training body",  "keyword": "운동,헬스,다이어트,홈트,피트니스,근력운동,살빼기"},
    "ch04": {"name": "딥슬립룸",    "category": "ASMR",   "tone": "조용하고 편안한",        "pexels_query": "rain forest nature sleep calm",     "keyword": "ASMR,수면,힐링,백색소음,잠잘때,빗소리,자연소리"},
    "ch05": {"name": "몽글클럽",    "category": "반려동물","tone": "귀엽고 따뜻한",          "pexels_query": "cute puppy kitten cat dog playing", "keyword": "강아지,고양이,반려동물,귀여운,펫,동물,멍냥이"},
    "ch06": {"name": "픽앤리뷰",    "category": "리뷰",    "tone": "솔직하고 유익한",        "pexels_query": "product review lifestyle shopping",  "keyword": "리뷰,추천,꿀팁,솔직후기,언박싱,최신템,가성비"},
    "ch07": {"name": "이슈타르",    "category": "이슈",    "tone": "흥미롭고 자극적인",      "pexels_query": "city people urban crowd news",      "keyword": "이슈,뉴스,화제,요즘,핫이슈,최신이슈,충격"},
    "ch08": {"name": "뷰티끄",      "category": "뷰티",    "tone": "세련되고 트렌디한",      "pexels_query": "beauty makeup skincare cosmetic",   "keyword": "뷰티,화장,스킨케어,메이크업,뷰티팁,피부관리,화장법"},
    "ch09": {"name": "한끼스케치",  "category": "음식",    "tone": "맛있고 식욕자극하는",    "pexels_query": "korean food cooking delicious meal","keyword": "음식,맛집,요리,먹방,레시피,맛있는,음식추천"},
    "ch10": {"name": "무비착",      "category": "영화",    "tone": "흥미롭고 분석적인",      "pexels_query": "cinema film dramatic popcorn",      "keyword": "영화,드라마,리뷰,추천영화,명장면,영화추천,넷플릭스"},
    "ch11": {"name": "룩북노트",    "category": "패션",    "tone": "세련되고 트렌디한",      "pexels_query": "fashion style outfit street look",  "keyword": "패션,코디,룩북,스타일,옷추천,패션팁,데일리룩"},
    "ch12": {"name": "드라마찜",    "category": "드라마",  "tone": "감동적이고 공감가는",    "pexels_query": "couple romantic drama emotional",   "keyword": "드라마,명장면,OST,한드,드라마추천,드라마리뷰"},
    "ch13": {"name": "트래블로그",  "category": "여행",    "tone": "설레고 신나는",          "pexels_query": "travel landscape beautiful scenery","keyword": "여행,국내여행,해외여행,여행지,여행팁,여행vlog"},
    "ch14": {"name": "퀴즈는",      "category": "퀴즈",    "tone": "재미있고 도전적인",      "pexels_query": "quiz thinking brain game challenge","keyword": "퀴즈,상식,문제,맞춰봐,두뇌게임,퀴즈게임"},
    "ch15": {"name": "밈스토리",    "category": "밈",      "tone": "유머러스하고 공감가는",  "pexels_query": "funny comedy laugh humor people",   "keyword": "밈,웃긴영상,유머,공감,웃음,개그,현실공감"},
}

# 채널별 후킹 제목 템플릿
TITLE_HOOKS = {
    "명언": ["이 말 한마디가 내 인생을 바꿨다", "오늘 꼭 봐야 할 명언", "모르면 손해인 인생 명언", "당신에게 필요한 말"],
    "노래": ["지금 당장 듣고 싶은 노래", "이 노래 모르면 아쉬울걸요", "감성 터지는 플레이리스트", "오늘 분위기엔 이 노래"],
    "운동": ["이것만 해도 살 빠진다", "하루 5분으로 몸이 달라진다", "운동 전 꼭 봐야 할 영상", "이 운동 안하면 후회한다"],
    "ASMR": ["잠 못 드는 밤에 틀어봐", "스트레스 날리는 소리", "이거 들으면 5분 안에 잠든다", "마음이 편해지는 소리"],
    "반려동물": ["이 영상 보면 힐링된다", "너무 귀여워서 심장 터질뻔", "세상에서 제일 귀여운 순간", "보는 순간 미소짓게 되는"],
    "리뷰": ["이거 살까 말까 고민된다면", "솔직하게 말해드릴게요", "이거 진짜 써봤는데요", "구매 전 꼭 봐야 할 영상"],
    "이슈": ["이거 실화냐", "지금 난리난 이슈", "알고 보면 충격적인", "이 사실 몰랐죠"],
    "뷰티": ["이 방법 왜 이제 알았을까", "피부 좋아지는 꿀팁", "뷰티 유튜버들이 숨기는 비법", "10분만에 달라지는 방법"],
    "음식": ["이거 안먹어봤으면 손해", "지금 당장 먹고싶은", "이 맛 알면 못 끊는다", "오늘 뭐 먹을지 고민된다면"],
    "영화": ["이 영화 안봤으면 지금 당장", "봤다면 공감할 장면", "결말이 충격적인 영화", "인생 영화 추가됩니다"],
    "패션": ["이 코디 진짜 예쁘다", "오늘 뭐 입을지 고민된다면", "이것만 있으면 스타일 완성", "패피들이 즐겨 입는"],
    "드라마": ["이 장면에서 다 울었다", "드라마 보다가 멈춘 명장면", "이 드라마 안보면 후회", "OST 들으면 그 장면이"],
    "여행": ["여기 진짜 가보고 싶다", "이 여행지 아는 사람", "가면 반드시 후회없는 곳", "여행 계획 있다면 꼭 봐"],
    "퀴즈": ["이거 맞추면 천재", "100명 중 5명만 맞춘다", "다들 틀리는 상식 문제", "자신있으면 도전해봐"],
    "밈": ["이거 보고 웃으면 정상", "공감 100% 상황", "이 상황 나만 겪은거 아니지", "현실 공감 터지는 순간"],
}

upload_log = []
toast_queue = []
pipeline_status = {}

def log(msg, level="info", toast=False):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info": "ℹ️", "ok": "✅", "err": "❌", "warn": "⚠️"}.get(level, "•")
    entry = f"[{ts}] {icon} {msg}"
    upload_log.append({"time": ts, "level": level, "msg": msg, "full": entry})
    print(entry)
    if toast:
        toast_queue.append({"msg": msg, "level": level, "time": ts})

# ==================== Gemini AI 대본+제목 ====================
def generate_content_claude(channel_id):
    ch = YOUTUBE_CHANNELS[channel_id]
    category = ch['category']

    # 랜덤 주제
    topics = {
        "명언": ["성공", "도전", "희망", "용기", "행복", "사랑", "성장", "꿈", "감사", "극복"],
        "운동": ["스쿼트", "플랭크", "유산소", "근력", "홈트", "다이어트", "복근", "상체"],
        "ASMR": ["빗소리", "파도소리", "모닥불", "숲속", "카페소음", "수면", "명상"],
        "반려동물": ["강아지", "고양이", "산책", "목욕", "훈련", "간식", "놀이"],
        "음식": ["한식", "디저트", "야식", "건강식", "간식", "레시피", "분식"],
        "영화": ["액션", "로맨스", "공포", "코미디", "SF", "감동", "추천"],
        "패션": ["캐주얼", "데이트룩", "오피스룩", "미니멀", "트렌드", "계절코디"],
        "드라마": ["로맨스", "스릴러", "코미디", "사극", "의학", "감동"],
        "여행": ["제주도", "부산", "서울", "경주", "일본", "유럽", "동남아"],
        "퀴즈": ["역사", "과학", "지리", "연예인", "음식", "영화", "상식"],
        "밈": ["공감짤", "직장인", "학생", "연인", "현실공감", "유행어"],
        "이슈": ["연예", "사회", "경제", "스포츠", "해외토픽", "화제"],
        "뷰티": ["스킨케어", "메이크업", "헤어", "네일", "선크림", "립"],
        "리뷰": ["맛집", "제품", "앱", "서비스", "가성비템"],
        "노래": ["발라드", "팝", "힙합", "R&B", "인디", "OST"],
    }
    topic_list = topics.get(category, ["꿀팁", "정보", "추천"])
    random_topic = random.choice(topic_list)
    hook = random.choice(TITLE_HOOKS.get(category, ["꼭 봐야 할"]))

    try:
        gemini_keys = config.get("GEMINI_API_KEYS", [])
        if not gemini_keys:
            raise Exception("Gemini 키 없음")

        # 키 돌아가며 사용 (랜덤)
        gemini_key = random.choice(gemini_keys)

        prompt = f"""한국 유튜브 쇼츠 전문 크리에이터로서 JSON만 출력하세요.

채널: {ch['name']} ({category} 채널)
주제: {random_topic}
톤: {ch['tone']}
후킹제목힌트: {hook}

아래 형식 JSON만 출력 (다른 텍스트 없이):
{{
  "title": "이모지1개+후킹문구+{random_topic} 관련 (25자이내, 클릭하고싶게)",
  "script": "안녕하세요! {ch['name']}입니다로 시작. {random_topic}에 대한 핵심 내용 2-3문장. 마지막에 구독/좋아요 유도 멘트. 총 20초 분량.",
  "tags": "{category},{random_topic},쇼츠,유튜브쇼츠,{ch['name']}",
  "description": "{ch['name']} 채널 | {random_topic} 관련 꿀팁!\\n매일 업로드 🔔구독하고 놓치지 마세요!\\n#쇼츠 #{category} #{random_topic}"
}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 600}
        }
        res = requests.post(url, json=data, timeout=30)
        res_json = res.json()
        result = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = result.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(result)
        log(f"✅ Gemini 제목: {parsed.get('title','')}", "ok")
        return parsed
    except Exception as e:
        log(f"Claude 오류: {e} → 기본값", "warn")
        return {
            "title": f"✨ {hook} {random_topic}",
            "script": f"안녕하세요! {ch['name']}입니다! 오늘은 {random_topic}에 대한 꿀팁을 알려드릴게요! 정말 유용한 정보니까 끝까지 봐주세요! 구독과 좋아요 부탁드려요!",
            "tags": f"{category},{random_topic},쇼츠,유튜브쇼츠",
            "description": f"{ch['name']} | {random_topic} 꿀팁!\n매일 업로드 🔔\n#쇼츠 #{category}"
        }

# ==================== Pexels 실시간 영상 ====================
def get_pexels_video(channel_id):
    ch = YOUTUBE_CHANNELS[channel_id]
    if not PEXELS_API_KEY or PEXELS_API_KEY.startswith("여기에"):
        return None
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        page = random.randint(1, 8)
        res = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": ch['pexels_query'], "per_page": 15, "page": page, "orientation": "portrait"},
            timeout=30
        )
        videos = res.json().get("videos", [])
        if not videos:
            res2 = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": ch['category'], "per_page": 10, "page": 1, "orientation": "portrait"},
                timeout=30
            )
            videos = res2.json().get("videos", [])
        if not videos:
            return None

        video = random.choice(videos)
        # 세로형 우선 선택
        video_files = [f for f in video["video_files"] if f.get("height", 0) > f.get("width", 0)]
        if not video_files:
            video_files = video["video_files"]
        video_files = sorted(video_files, key=lambda x: x.get("height", 0), reverse=True)
        video_url = video_files[0]["link"]

        video_path = OUTPUT_DIR / f"{channel_id}_pexels.mp4"
        log(f"[{ch['name']}] Pexels 영상 다운로드 중...", "info")
        r = requests.get(video_url, stream=True, timeout=90)
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        log(f"[{ch['name']}] Pexels 완료!", "ok")
        return video_path
    except Exception as e:
        log(f"Pexels 오류: {e}", "warn")
        return None

# ==================== Runway AI 4K ====================
def generate_runway_video(channel_id, prompt_text):
    ch = YOUTUBE_CHANNELS[channel_id]
    if not RUNWAY_API_KEY or RUNWAY_API_KEY.startswith("여기에"):
        return None
    try:
        runway_key = RUNWAY_API_KEY
        if not runway_key.startswith("key_"):
            runway_key = f"key_{runway_key}"
        headers = {
            "Authorization": f"Bearer {runway_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06"
        }
        data = {
            "promptText": f"{ch['pexels_query']}, vertical 9:16, 4K cinematic",
            "model": "gen3a_turbo",
            "duration": 5,
            "ratio": "768:1280"
        }
        log(f"[{ch['name']}] Runway AI 4K 생성 중...", "info")
        res = requests.post("https://api.dev.runwayml.com/v1/image_to_video",
                          headers=headers, json=data, timeout=30)
        task_id = res.json().get("id")
        if not task_id:
            return None
        for i in range(25):
            time.sleep(3)
            s = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                           headers=headers, timeout=15).json()
            if s.get("status") == "SUCCEEDED":
                video_path = OUTPUT_DIR / f"{channel_id}_runway.mp4"
                r = requests.get(s["output"][0], stream=True, timeout=90)
                with open(video_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                log(f"[{ch['name']}] Runway 완료!", "ok", toast=True)
                return video_path
            elif s.get("status") == "FAILED":
                break
        return None
    except Exception as e:
        log(f"Runway 오류: {e}", "warn")
        return None

# ==================== 음성 생성 ====================
def make_voice(script, channel_id):
    audio_path = OUTPUT_DIR / f"{channel_id}_voice.mp3"
    try:
        tts = gTTS(text=script, lang='ko', slow=False)
        tts.save(str(audio_path))
        log(f"음성 생성 완료", "ok")
        return audio_path
    except Exception as e:
        log(f"음성 오류: {e}", "err")
        return None

# ==================== 자막 생성 ====================
def make_subtitle(script, channel_id):
    srt_path = SUBTITLES_DIR / f"{channel_id}.srt"
    try:
        sentences = re.split(r'[.!?]', script)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 1]
        if not sentences:
            sentences = [script]

        srt_content = ""
        start = 0.0
        for i, sentence in enumerate(sentences, 1):
            duration = max(2.0, len(sentence) * 0.13)
            end = start + duration
            def fmt(t):
                h, rem = divmod(int(t), 3600)
                m, s = divmod(rem, 60)
                ms = int((t - int(t)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            srt_content += f"{i}\n{fmt(start)} --> {fmt(end)}\n{sentence}\n\n"
            start = end + 0.3

        with open(srt_path, "w", encoding="utf-8-sig") as f:
            f.write(srt_content)
        log(f"자막 생성 완료: {len(sentences)}문장", "ok")
        return srt_path
    except Exception as e:
        log(f"자막 오류: {e}", "warn")
        return None

# ─── output 폴더에서 영상 찾기 ───────────────────────────────
def get_video_for_channel(ch_id):
    """output/ch01_final.mp4 → output/ch15_final.mp4 찾기"""
    # 1순위: ch01_final.mp4
    final = OUTPUT_DIR / f"{ch_id}_final.mp4"
    if final.exists():
        return final

    # 2순위: ch01_pexels.mp4
    pexels = OUTPUT_DIR / f"{ch_id}_pexels.mp4"
    if pexels.exists():
        return pexels

    # 3순위: output 폴더의 아무 mp4
    mp4s = list(OUTPUT_DIR.glob("*.mp4"))
    if mp4s:
        return mp4s[0]

    log(f"[{ch_id}] 업로드할 영상 없음! output/ 폴더 확인하세요", "err")
    return None

# ─── YouTube 업로드 ───────────────────────────────────────────
def upload_to_youtube(ch_id, video_path):
    ch      = CHANNELS[ch_id]
    youtube = get_youtube_service(ch_id)
    if not youtube:
        return False

    title = f"{ch['name']} {datetime.now().strftime('%m월%d일')} #{ch['category']} #shorts"
    body  = {
        "snippet": {
            "title":       title,
            "description": f"#{ch['category']} #슬다 #쇼츠 #shorts",
            "tags":        [ch["category"], "쇼츠", "슬다", "shorts"],
            "categoryId":  "22",
        },
        "status": {
            "privacyStatus":          "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    try:
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        req   = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        log(f"[{ch['name']}] 업로드 중... ({video_path.name})", "info")
        while response is None:
            _, response = req.next_chunk()
        vid_id = response.get("id", "")
        log(f"[{ch['name']}] ✅ 업로드 완료! https://youtube.com/shorts/{vid_id}", "ok")
        return True
    except Exception as e:
        log(f"[{ch['name']}] 업로드 오류: {str(e)[:300]}", "err")
        return False

# ─── 전체 파이프라인 ──────────────────────────────────────────
def run_pipeline(channel_ids, script=None):
    upload_stats["running"] = True
    results = {"success": [], "fail": []}

    for ch_id in channel_ids:
        if ch_id not in CHANNELS:
            continue
        ch_name = CHANNELS[ch_id]["name"]
        try:
            # output 폴더에서 영상 찾기
            video = get_video_for_channel(ch_id)
            if not video:
                results["fail"].append(ch_name)
                continue

            ok = upload_to_youtube(ch_id, video)
            (results["success"] if ok else results["fail"]).append(ch_name)
            time.sleep(3)

        except Exception as e:
            log(f"[{ch_name}] 오류: {e}", "err")
            results["fail"].append(ch_name)

    upload_stats["success"] += len(results["success"])
    upload_stats["fail"]    += len(results["fail"])
    upload_stats["running"]  = False
    log(f"🎉 완료! 성공:{len(results['success'])}개 실패:{len(results['fail'])}개", "ok")
        # 자막 필터 - Windows 경로 처리
        sub_filter = ""
        if subtitle_path and subtitle_path.exists():
            # Windows 경로를 ffmpeg 형식으로 변환
            sub_str = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:")
            sub_filter = (
                f",subtitles='{sub_str}'"
                f":force_style='FontName=Malgun Gothic,"
                f"FontSize=24,Bold=1,"
                f"PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,"
                f"Outline=3,Shadow=1,"
                f"Alignment=2,MarginV=80'"
            )

        cmd = [
            FFMPEG_EXE, "-y",
            "-i", str(base_video),
            "-i", str(audio_path),
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-vf", base_vf + sub_filter,
            str(output_path)
        ]
        log(f"[{channel_id}] 영상 합성 중...", "info")
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="ignore", timeout=180)

        if result.returncode != 0 or not output_path.exists():
            log(f"자막 합성 실패 → 자막 없이 재시도", "warn")
            cmd2 = [
                FFMPEG_EXE, "-y",
                "-i", str(base_video),
                "-i", str(audio_path),
                "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                "-vf", base_vf,
                str(output_path)
            ]
            subprocess.run(cmd2, capture_output=True, timeout=180)

        if output_path.exists():
            size_mb = output_path.stat().st_size / 1024 / 1024
            log(f"영상 합성 완료! ({size_mb:.1f}MB)", "ok")
            return output_path
        return None
    except Exception as e:
        log(f"영상 합성 오류: {e}", "err")
        return None

# ─── YouTube API 인증 ─────────────────────────────────────────
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
# ==================== YouTube 업로드 ====================
def upload_youtube(channel_id, video_path, content):
    ch = YOUTUBE_CHANNELS[channel_id]
    pipeline_status[channel_id] = "업로드 중"
    try:
        youtube = get_youtube_service(channel_id)
        tags = [t.strip() for t in content.get("tags", "").split(",")][:15]
        body = {
            "snippet": {
                "title": content.get("title", f"✨ {ch['name']} 쇼츠"),
                "description": content.get("description", f"{ch['name']} 채널입니다!"),
                "tags": tags,
                "categoryId": "22",
                "defaultLanguage": "ko",
                "defaultAudioLanguage": "ko"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                               resumable=True, chunksize=1024*1024*5)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = req.next_chunk()
            if status:
                log(f"[{ch['name']}] 업로드 {int(status.progress()*100)}%", "info")
        video_id = response.get("id", "")
        log(f"[{ch['name']}] ✅ 업로드 완료! 제목: {content.get('title','')} | https://youtube.com/shorts/{video_id}", "ok", toast=True)
        pipeline_status[channel_id] = "완료"
        return True
    except Exception as e:
        log(f"[{ch['name']}] 업로드 오류: {str(e)[:200]}", "err", toast=True)
        pipeline_status[channel_id] = "실패"
        return False

# ==================== 메인 파이프라인 ====================
def run_pipeline(channel_ids, script=None):
    total = len(channel_ids)
    log(f"🚀 {total}개 채널 시작!", "ok", toast=True)

    videos_local = []
    if VIDEO_POOL_DIR.exists():
        videos_local = sorted([v for v in VIDEO_POOL_DIR.glob("*.mp4")
                               if "4k" not in v.name.lower()])

    results = {"success": [], "fail": []}

    for i, ch_id in enumerate(channel_ids, 1):
        if ch_id not in YOUTUBE_CHANNELS:
            continue
        ch = YOUTUBE_CHANNELS[ch_id]
        pipeline_status[ch_id] = "진행중"
        log(f"━━ [{i}/{total}] {ch['name']} 시작 ━━", "info", toast=True)

        try:
            # 1. AI 대본+제목
            content = generate_content_claude(ch_id)
            use_script = script if script else content.get("script", "")
            log(f"[{ch['name']}] 제목: {content.get('title','')}", "info")

            # 2. 영상 (Pexels → Runway → 로컬)
            base_video = get_pexels_video(ch_id)
            if not base_video:
                base_video = generate_runway_video(ch_id, use_script)
            if not base_video and videos_local:
                idx = (int(ch_id.replace("ch", "")) - 1) % len(videos_local)
                base_video = videos_local[idx]
                log(f"[{ch['name']}] 로컬 영상 사용", "info")
            if not base_video:
                log(f"[{ch['name']}] 영상 없음!", "err")
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            # 3. 음성
            audio = make_voice(use_script, ch_id)
            if not audio:
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            # 4. 자막
            subtitle = make_subtitle(use_script, ch_id)

            # 5. 영상 합성
            video = make_video(ch_id, base_video, audio, subtitle)
            if not video:
                results["fail"].append(ch["name"])
                pipeline_status[ch_id] = "실패"
                continue

            # 6. 업로드
            ok = upload_youtube(ch_id, video, content)
            (results["success"] if ok else results["fail"]).append(ch["name"])

            wait = random.randint(10, 25)
            log(f"⏱ {wait}초 대기...", "info")
            time.sleep(wait)

        except Exception as e:
            log(f"[{ch['name']}] 오류: {e}", "err", toast=True)
            results["fail"].append(ch["name"])
            pipeline_status[ch_id] = "실패"

    log(f"🎉 완료! 성공:{len(results['success'])}개 실패:{len(results['fail'])}개", "ok", toast=True)

# ==================== 자동 스케줄러 (아침/점심/저녁 3라운드) ====================
import schedule as sch

# 15개 채널 순서
ALL_CHANNELS = list(YOUTUBE_CHANNELS.keys())  # ch01 ~ ch15

def auto_upload_round(round_name):
    """아침/점심/저녁 라운드 - 15개 채널 순서대로 업로드"""
    log(f"🕐 [{round_name}] 자동 업로드 시작! 15개 채널", "ok", toast=True)
    threading.Thread(
        target=run_pipeline,
        args=(ALL_CHANNELS, ""),
        daemon=True
    ).start()

def setup_schedule():
    """스케줄 등록 - 아침/점심/저녁 각 1라운드"""
    # 🌅 아침 라운드 (09:00)
    sch.every().day.at("09:00").do(auto_upload_round, "🌅 아침")
    # ☀️ 점심 라운드 (13:00)
    sch.every().day.at("13:00").do(auto_upload_round, "☀️ 점심")
    # 🌙 저녁 라운드 (19:00)
    sch.every().day.at("19:00").do(auto_upload_round, "🌙 저녁")

    log("⏰ 스케줄 등록 완료!", "ok")
    log("🌅 아침 09:00 → 15채널 자동 업로드", "info")
    log("☀️ 점심 13:00 → 15채널 자동 업로드", "info")
    log("🌙 저녁 19:00 → 15채널 자동 업로드", "info")
    log("📊 하루 총 45개 업로드 (채널당 3개)", "info")

    # 스케줄 실행 루프 (백그라운드)
    def run_loop():
        while True:
            sch.run_pending()
            time.sleep(30)

    threading.Thread(target=run_loop, daemon=True).start()

# ==================== Flask ====================
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>슬다 자동화</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0b0f19;color:#f1f5f9;padding:12px;max-width:480px;margin:0 auto;min-height:100vh}
h1{font-size:20px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:2px}
.sub{color:#475569;font-size:10px;margin-bottom:12px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}
.stat{background:#1e293b;border-radius:10px;padding:10px;text-align:center}
.stat-num{font-size:24px;font-weight:800}
.stat-label{font-size:9px;color:#475569;margin-top:2px}
.progress-bar{background:#1e293b;border-radius:6px;height:6px;margin-bottom:10px;overflow:hidden}
.progress-fill{height:100%;background:linear-gradient(90deg,#3b82f6,#8b5cf6);border-radius:6px;transition:width .5s;width:0%}
.sb{background:#1e293b;border-radius:10px;padding:8px 12px;margin-bottom:10px;font-size:10px;color:#64748b;display:flex;gap:12px;flex-wrap:wrap}
.ok{color:#4ade80;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:10px}
.card{background:#1e293b;border:1.5px solid #334155;border-radius:10px;padding:8px 4px;cursor:pointer;transition:all .15s;text-align:center;user-select:none}
.card:active{transform:scale(.95)}
.card.sel{border-color:#3b82f6;background:#1e3a5f}
.card.done{border-color:#4ade80!important;background:#052e16!important}
.card.fail{border-color:#f87171!important;background:#2d0707!important}
.card.running{border-color:#fbbf24!important;background:#2d1f00!important;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.cn{font-size:10px;font-weight:700}.cc{font-size:8px;color:#64748b;margin-top:1px}.cs{font-size:10px;margin-top:1px}
.br{display:flex;gap:6px;margin-bottom:8px}
button{padding:10px 12px;border-radius:10px;border:none;cursor:pointer;font-size:12px;font-weight:700;transition:all .15s}
button:active{transform:scale(.97)}
.bb{background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;flex:1;padding:16px;font-size:16px;border-radius:12px;box-shadow:0 4px 15px rgba(59,130,246,.3)}
.bg{background:#1e293b;color:#94a3b8;border:1px solid #334155}
textarea{width:100%;background:#1e293b;border:1.5px solid #334155;border-radius:10px;color:#f1f5f9;padding:10px;font-size:13px;resize:vertical;min-height:55px;margin-bottom:8px;font-family:inherit}
textarea:focus{outline:none;border-color:#3b82f6}
.lb{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px;height:180px;overflow-y:auto;font-family:'Courier New',monospace;font-size:10px;line-height:1.6}
.lo{color:#4ade80}.le{color:#f87171}.lw{color:#fbbf24}.li{color:#64748b}
.lbl{font-size:10px;color:#475569;margin-bottom:5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
#toastContainer{position:fixed;top:10px;right:10px;z-index:9999;display:flex;flex-direction:column;gap:5px;max-width:240px}
.toast{background:#1e293b;border-radius:10px;padding:9px 12px;font-size:11px;animation:slideIn .3s ease;box-shadow:0 4px 20px rgba(0,0,0,.6);line-height:1.4}
.toast.ok{border-left:3px solid #4ade80}.toast.err{border-left:3px solid #f87171}
.toast.info{border-left:3px solid #3b82f6}.toast.warn{border-left:3px solid #fbbf24}
@keyframes slideIn{from{transform:translateX(110%);opacity:0}to{transform:translateX(0);opacity:1}}
.tip{background:linear-gradient(135deg,#1e3a5f,#1e293b);border:1px solid #3b82f6;border-radius:10px;padding:8px 12px;font-size:10px;color:#93c5fd;margin-bottom:10px}
</style>
</head>
<body>
<div id="toastContainer"></div>
<h1>⚡ 슬다 자동화</h1>
<p class="sub">v11.0 · Claude AI · Pexels실시간 · 자막 · 모바일</p>
<div class="tip">💡 대본 비우면 AI가 채널별 맞춤 제목+대본 자동 생성!</div>

<div class="stats">
  <div class="stat"><div class="stat-num" style="color:#4ade80" id="statSuccess">0</div><div class="stat-label">✅ 성공</div></div>
  <div class="stat"><div class="stat-num" style="color:#fbbf24" id="statRunning">0</div><div class="stat-label">⏳ 진행중</div></div>
  <div class="stat"><div class="stat-num" style="color:#f87171" id="statFail">0</div><div class="stat-label">❌ 실패</div></div>
</div>
<div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
<div class="sb">
  <span>FFmpeg <span id="ffSt">...</span></span>
  <span>영상 <span id="vidCnt" class="ok">-</span>개</span>
  <span>인증 <span id="tokenCnt" class="ok">-</span>/15</span>
</div>

<div class="lbl">채널 선택</div>
<div class="grid" id="channelGrid"></div>
<div class="br">
  <button class="bg" onclick="selectAll()" style="flex:1">전체선택</button>
  <button class="bg" onclick="clearAll()" style="flex:1">전체해제</button>
</div>
<div class="lbl">대본 (비워두면 AI 자동생성!)</div>
<textarea id="scriptText" placeholder="비워두면 채널별 맞춤 대본+제목 자동 생성!"></textarea>
<div class="br"><button class="bb" onclick="startUpload()">🚀 업로드 시작</button></div>
<div class="br"><button class="bg" onclick="clearLog()" style="width:100%">🗑 로그 초기화</button></div>
<div class="lbl">실행 로그</div>
<div class="lb" id="logBox"><div class="li">대기 중...</div></div>

<script>
const channels={{ channels|tojson }};
let sel=new Set();
function renderGrid(){
  document.getElementById('channelGrid').innerHTML=Object.entries(channels).map(([id,ch])=>
    `<div class="card" id="c${id}" onclick="tog('${id}')">
      <div class="cn">${ch.name}</div>
      <div class="cc">${ch.category}</div>
      <div class="cs" id="s${id}"></div>
    </div>`).join('');
}
function tog(id){
  const el=document.getElementById('c'+id);
  if(sel.has(id)){sel.delete(id);el.classList.remove('sel');}
  else{sel.add(id);el.classList.add('sel');}
}
function selectAll(){Object.keys(channels).forEach(id=>{sel.add(id);const el=document.getElementById('c'+id);if(!el.classList.contains('done')&&!el.classList.contains('running'))el.classList.add('sel');});}
function clearAll(){sel.forEach(id=>document.getElementById('c'+id).classList.remove('sel'));sel.clear();}
function showToast(msg,level='info'){
  const c=document.getElementById('toastContainer');
  const t=document.createElement('div');
  t.className=`toast ${level}`;t.textContent=msg;c.appendChild(t);
  setTimeout(()=>t.style.opacity='0',3500);setTimeout(()=>t.remove(),4000);
}
function startUpload(){
  if(sel.size===0){showToast('채널을 먼저 선택하세요!','warn');return;}
  fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({channels:[...sel],script:document.getElementById('scriptText').value})})
  .then(r=>r.json()).then(d=>showToast(d.msg,'ok'));
}
function clearLog(){document.getElementById('logBox').innerHTML='<div class="li">로그 초기화</div>';}
function pollLog(){fetch('/logs').then(r=>r.json()).then(logs=>{const b=document.getElementById('logBox');b.innerHTML=logs.map(l=>`<div class="l${l.level[0]}">${l.full}</div>`).join('')||'<div class="li">없음</div>';b.scrollTop=b.scrollHeight;}).catch(()=>{});}
function pollToast(){fetch('/toasts').then(r=>r.json()).then(t=>t.forEach(x=>showToast(x.msg,x.level))).catch(()=>{});}
function pollStatus(){
  fetch('/pipeline_status').then(r=>r.json()).then(data=>{
    let s=0,r=0,f=0;
    Object.entries(data.statuses).forEach(([id,status])=>{
      const card=document.getElementById('c'+id),sl=document.getElementById('s'+id);
      if(!card)return;
      card.classList.remove('done','fail','running');
      if(!sel.has(id))card.classList.remove('sel');
      if(status==='완료'){card.classList.add('done');s++;if(sl)sl.textContent='✅';}
      else if(status==='실패'){card.classList.add('fail');f++;if(sl)sl.textContent='❌';}
      else if(status==='진행중'||status==='업로드 중'){card.classList.add('running');r++;if(sl)sl.textContent='⏳';}
    });
    document.getElementById('statSuccess').textContent=s;
    document.getElementById('statRunning').textContent=r;
    document.getElementById('statFail').textContent=f;
    const total=Object.keys(data.statuses).length;
    if(total>0)document.getElementById('progressFill').style.width=((s+f)/total*100)+'%';
  }).catch(()=>{});
}
function checkSt(){fetch('/status').then(r=>r.json()).then(s=>{document.getElementById('ffSt').textContent=s.ffmpeg?'✅':'❌';document.getElementById('vidCnt').textContent=s.video_count;document.getElementById('tokenCnt').textContent=s.token_count;}).catch(()=>{});}
renderGrid();checkSt();
setInterval(pollLog,2000);setInterval(pollToast,1500);setInterval(pollStatus,2000);setInterval(checkSt,20000);
</script>
</body>
</html>"""

@app.route("/")
def dashboard():
    return render_template_string(HTML, channels=YOUTUBE_CHANNELS)

@app.route("/status")
def status():
    videos = []
    if VIDEO_POOL_DIR.exists():
        videos = [v for v in VIDEO_POOL_DIR.glob("*.mp4") if "4k" not in v.name.lower()]
    tokens = list(TOKENS_DIR.glob("*.pickle"))
    # 다음 스케줄 시간 계산
    next_job = sch.next_run()
    next_str = next_job.strftime("%H:%M") if next_job else "-"
    return jsonify({
        "ffmpeg": Path(FFMPEG_EXE).exists(),
        "video_count": len(videos),
        "token_count": len(tokens),
        "next_upload": next_str,
        "schedule": "🌅09:00 ☀️13:00 🌙19:00"
    })

@app.route("/run", methods=["POST"])
def run():
    data = flask_request.json
    threading.Thread(target=run_pipeline, args=(data.get("channels",[]), data.get("script","")), daemon=True).start()
    return jsonify({"status":"ok","msg":f"🚀 {len(data.get('channels',[]))}개 채널 업로드 시작!"})

@app.route("/logs")
def get_logs():
    return jsonify(upload_log[-100:])

@app.route("/toasts")
def get_toasts():
    toasts=toast_queue.copy();toast_queue.clear();return jsonify(toasts)

@app.route("/pipeline_status")
def get_pipeline_status():
    return jsonify({"statuses":pipeline_status})

if __name__=="__main__":
    log("슬다 자동화 v12.0 시작 🚀","ok",toast=True)
    log("PC: http://127.0.0.1:5000","info")
    log("모바일: http://192.168.219.116:5000","info")
    log(f"config.json 확인: {CONFIG_FILE}","info")

    # ✅ 스케줄 자동 등록 (아침/점심/저녁)
    setup_schedule()

    while True:
        try:
            app.run(host="0.0.0.0",port=5000,debug=False)
        except Exception as e:
            log(f"서버 오류: {e} → 10초 후 재시작","err")
            time.sleep(10)
