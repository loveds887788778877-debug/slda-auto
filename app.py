#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
슬다 자동화 v15.5
- Gemini 키 필터링 수정 (단일/배열 둘 다 지원)
- 채널별 맞춤 해시태그 10개 자동 생성 (매일 트렌드 반영)
- AI 슬다 영상 (ElevenLabs TTS + Pexels)
- Kling 잔액 부족 시 자동 폴백
- 09:00 업로드 실패 방지 (Gemini 없으면 기본 대본 사용)
"""

import os, json, time, random, schedule, threading, logging, pickle, re
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import google.generativeai as genai
import tempfile, subprocess

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger(__name__)

app = Flask(__name__)

# ─────────────────────────────────────────
# ① GEMINI 키 설정 (단일 + 배열 둘 다 지원)
# ─────────────────────────────────────────
def load_gemini_keys():
    keys = []
    # 배열 형태: GEMINI_API_KEYS
    raw = os.environ.get('GEMINI_API_KEYS', '')
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                keys.extend([k.strip() for k in parsed if k.strip()])
            elif isinstance(parsed, str):
                keys.append(parsed.strip())
        except:
            keys.append(raw.strip())
    # 단일 형태: GEMINI_API_KEY
    single = os.environ.get('GEMINI_API_KEY', '').strip()
    if single and single not in keys:
        keys.append(single)
    # 필터: 유효한 키만 (AIzaSy 또는 AI로 시작)
    valid = [k for k in keys if k.startswith('AI') and len(k) > 20]
    log.info(f"OK 유효한 Gemini 키: {len(valid)}개")
    return valid

GEMINI_KEYS = load_gemini_keys()
GEMINI_INDEX = [0]

def get_gemini_client():
    """키 순환하며 Gemini 클라이언트 반환"""
    if not GEMINI_KEYS:
        return None
    for attempt in range(len(GEMINI_KEYS)):
        idx = GEMINI_INDEX[0] % len(GEMINI_KEYS)
        key = GEMINI_KEYS[idx]
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            return model
        except Exception as e:
            log.warning(f"Gemini 키 [{idx}] 실패: {e}")
            GEMINI_INDEX[0] += 1
    return None

PEXELS_KEY = os.environ.get('PEXELS_API_KEY', '')
ELEVENLABS_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
KLING_KEY = os.environ.get('KLING_API_KEY', '')

# ─────────────────────────────────────────
# ② 채널 구성 (12개 자동화 채널)
# ─────────────────────────────────────────
CHANNELS = {
    'ch01': {'name': '한줄의린', 'topic': '명언/동기부여', 'keyword': '명언 동기부여 힐링', 'color': '#FF6B6B'},
    'ch02': {'name': '무드웨이브', 'topic': '음악/감성', 'keyword': '감성 음악 무드', 'color': '#4ECDC4'},
    'ch03': {'name': '피트노트', 'topic': '운동/건강', 'keyword': '운동 헬스 건강', 'color': '#45B7D1'},
    'ch04': {'name': '딥슬립룸', 'topic': 'ASMR/수면', 'keyword': 'ASMR 수면 백색소음', 'color': '#96CEB4'},
    'ch05': {'name': '몽글클럽', 'topic': '반려동물', 'keyword': '강아지 고양이 귀여운', 'color': '#FFEAA7'},
    'ch06': {'name': '픽앤리뷰', 'topic': '제품리뷰', 'keyword': '리뷰 추천 꿀템', 'color': '#DDA0DD'},
    'ch07': {'name': '이슈타르', 'topic': '이슈/정보', 'keyword': '이슈 정보 트렌드', 'color': '#98D8C8'},
    'ch08': {'name': '뷰티끄', 'topic': '뷰티/화장', 'keyword': '뷰티 메이크업 스킨케어', 'color': '#F7DC6F'},
    'ch09': {'name': '한끼스케치', 'topic': '음식/요리', 'keyword': '맛집 요리 음식', 'color': '#BB8FCE'},
    'ch10': {'name': '무비착', 'topic': '영화/드라마', 'keyword': '영화 드라마 리뷰', 'color': '#85C1E9'},
    'ch11': {'name': '룩북노트', 'topic': '패션/스타일', 'keyword': '패션 코디 룩북', 'color': '#F1948A'},
    'ch12': {'name': '드라마찜', 'topic': '드라마/연예', 'keyword': '드라마 연예인 인기', 'color': '#82E0AA'},
}

# ─────────────────────────────────────────
# ③ 채널별 맞춤 해시태그 10개 (매일 트렌드 반영)
# ─────────────────────────────────────────
HASHTAG_DB = {
    'ch01': {  # 명언/동기부여
        'base': ['#명언', '#동기부여', '#힐링', '#오늘의말한마디', '#긍정에너지'],
        'trend': ['#자기계발', '#성장', '#마음챙김', '#멘탈관리', '#인생명언',
                  '#좋은글', '#공감', '#위로', '#일상', '#감성'],
        'viral': ['#shorts', '#쇼츠', '#유튜브쇼츠', '#viral', '#trending']
    },
    'ch02': {  # 음악/감성
        'base': ['#감성', '#음악', '#무드', '#감성뮤직', '#플레이리스트'],
        'trend': ['#힐링음악', '#새벽감성', '#드라이브뮤직', '#공부할때듣는노래', '#빗소리',
                  '#재즈', '#로파이', '#감성팝', '#인디음악', '#뮤직'],
        'viral': ['#shorts', '#쇼츠', '#lofi', '#chill', '#vibes']
    },
    'ch03': {  # 운동/건강
        'base': ['#운동', '#헬스', '#건강', '#홈트', '#다이어트'],
        'trend': ['#헬린이', '#근성장', '#유산소', '#스트레칭', '#필라테스',
                  '#요가', '#러닝', '#바디프로필', '#식단', '#건강루틴'],
        'viral': ['#shorts', '#쇼츠', '#workout', '#fitness', '#gym']
    },
    'ch04': {  # ASMR/수면
        'base': ['#ASMR', '#수면', '#백색소음', '#릴렉스', '#힐링'],
        'trend': ['#빗소리ASMR', '#카페소리', '#자연소리', '#숙면', '#스트레스해소',
                  '#집중력', '#공부asmr', '#타자소리', '#불면증', '#수면음악'],
        'viral': ['#shorts', '#쇼츠', '#sleep', '#relaxing', '#asmr']
    },
    'ch05': {  # 반려동물
        'base': ['#강아지', '#고양이', '#반려동물', '#귀여운', '#펫'],
        'trend': ['#댕댕이', '#냥이', '#골든리트리버', '#말티즈', '#페르시안',
                  '#동물영상', '#웃긴동물', '#펫스타그램', '#멍스타그램', '#고양이스타그램'],
        'viral': ['#shorts', '#쇼츠', '#cute', '#funny', '#animals']
    },
    'ch06': {  # 제품리뷰
        'base': ['#리뷰', '#추천', '#꿀템', '#솔직리뷰', '#구매후기'],
        'trend': ['#신상', '#쿠팡', '#아마존', '#가성비', '#득템',
                  '#언박싱', '#써보고말함', '#진짜후기', '#필수템', '#인생템'],
        'viral': ['#shorts', '#쇼츠', '#review', '#unboxing', '#recommend']
    },
    'ch07': {  # 이슈/정보
        'base': ['#이슈', '#정보', '#트렌드', '#알아두면좋은', '#꿀정보'],
        'trend': ['#핫이슈', '#요즘이야기', '#생활정보', '#뉴스', '#실시간이슈',
                  '#오늘의이슈', '#화제', '#알고리즘', '#SNS이슈', '#인터넷이슈'],
        'viral': ['#shorts', '#쇼츠', '#trending', '#viral', '#이슈']
    },
    'ch08': {  # 뷰티
        'base': ['#뷰티', '#메이크업', '#스킨케어', '#화장품', '#뷰티팁'],
        'trend': ['#올리브영', '#신상화장품', '#데일리메이크업', '#피부관리', '#클렌징',
                  '#선크림', '#쿠션팩트', '#립스틱', '#아이섀도', '#뷰티루틴'],
        'viral': ['#shorts', '#쇼츠', '#beauty', '#makeup', '#skincare']
    },
    'ch09': {  # 음식/요리
        'base': ['#맛집', '#요리', '#음식', '#먹방', '#레시피'],
        'trend': ['#홈쿡', '#간단레시피', '#자취요리', '#다이어트식단', '#건강식',
                  '#서울맛집', '#혼밥', '#야식', '#디저트', '#카페'],
        'viral': ['#shorts', '#쇼츠', '#food', '#cooking', '#yummy']
    },
    'ch10': {  # 영화
        'base': ['#영화', '#드라마', '#리뷰', '#추천', '#영화추천'],
        'trend': ['#넷플릭스', '#디즈니플러스', '#왓챠', '#웨이브', '#티빙',
                  '#신작영화', '#영화리뷰', '#드라마추천', '#결말해석', '#명작'],
        'viral': ['#shorts', '#쇼츠', '#movie', '#netflix', '#drama']
    },
    'ch11': {  # 패션
        'base': ['#패션', '#코디', '#룩북', '#스타일', '#오오티디'],
        'trend': ['#데일리룩', '#봄코디', '#여름코디', '#가을코디', '#겨울코디',
                  '#자라', '#무신사', '#에이블리', '#트렌드', '#빈티지'],
        'viral': ['#shorts', '#쇼츠', '#fashion', '#ootd', '#style']
    },
    'ch12': {  # 드라마찜
        'base': ['#드라마', '#연예', '#인기드라마', '#드라마추천', '#연예인'],
        'trend': ['#넷플릭스드라마', '#tvN', '#MBC', '#KBS', '#SBS',
                  '#드라마리뷰', '#신작드라마', '#주말드라마', '#미니시리즈', '#로맨스드라마'],
        'viral': ['#shorts', '#쇼츠', '#kdrama', '#한드', '#드라마']
    },
}

def get_trending_hashtags(ch_id, date_seed=None):
    """채널별 오늘의 트렌드 해시태그 10개 생성"""
    if date_seed is None:
        date_seed = datetime.now().strftime('%Y%m%d')
    
    db = HASHTAG_DB.get(ch_id, HASHTAG_DB['ch07'])
    random.seed(int(date_seed) + hash(ch_id))
    
    # base 5개 고정 + trend에서 3개 랜덤 + viral 2개
    selected_trend = random.sample(db['trend'], min(3, len(db['trend'])))
    selected_viral = random.sample(db['viral'], 2)
    
    tags = db['base'] + selected_trend + selected_viral
    return tags[:10]  # 정확히 10개

# ─────────────────────────────────────────
# ④ 대본 생성 (Gemini 없으면 기본 대본 사용)
# ─────────────────────────────────────────
DEFAULT_SCRIPTS = {
    'ch01': ['하루를 바꾸는 한 마디. 오늘도 당신은 충분히 잘하고 있습니다. 포기하지 마세요. 작은 한 걸음이 큰 변화를 만들어냅니다. 오늘 하루도 화이팅!'],
    'ch02': ['감성 충전 시간. 지금 이 순간, 음악과 함께 잠깐 쉬어가세요. 마음이 따뜻해지는 선율로 오늘 하루를 마무리해보세요.'],
    'ch03': ['오늘의 운동 루틴! 10분만 투자해도 몸이 달라집니다. 홈트로 시작하는 건강한 하루, 같이 해볼까요?'],
    'ch04': ['편안한 수면을 위한 ASMR. 하루의 피로를 내려놓고 깊은 잠에 빠져드세요. 백색소음과 함께 꿀잠 자는 밤 되세요.'],
    'ch05': ['세상에서 제일 귀여운 순간. 오늘도 우리 아이들의 귀여운 모습에 힐링하고 가세요! 보는 것만으로도 행복해지는 영상입니다.'],
    'ch06': ['솔직한 리뷰 들어갑니다! 직접 써보고 말하는 진짜 후기. 사기 전에 꼭 보세요. 이건 진짜 꿀템입니다.'],
    'ch07': ['오늘의 핫이슈! 알아두면 좋은 정보를 전해드립니다. 트렌드를 놓치지 마세요. 구독하면 매일 유용한 정보를 받아보실 수 있어요.'],
    'ch08': ['오늘의 뷰티 팁! 간단하지만 효과적인 스킨케어 루틴을 공유합니다. 5분이면 피부가 달라져요. 같이 해봐요!'],
    'ch09': ['오늘 뭐 먹을까? 집에서 만드는 간단 레시피! 재료 몇 가지로 맛집 부럽지 않은 요리를 만들어보세요.'],
    'ch10': ['이번 주 꼭 봐야 할 영화/드라마 추천! 스트리밍 뭐 볼지 고민이라면 바로 여기서 답 찾아가세요.'],
    'ch11': ['오늘의 코디 추천! 이것저것 고민하지 말고 이 조합으로 입어보세요. 간단하지만 세련된 데일리 룩입니다.'],
    'ch12': ['요즘 핫한 드라마 정보! 놓치면 아쉬운 명장면과 결말 해석까지. 드라마 좋아한다면 구독 필수!'],
}

def generate_script(ch_id, topic, keyword):
    """Gemini로 대본 생성, 실패시 기본 대본 사용"""
    model = get_gemini_client()
    
    if model:
        try:
            ch_info = CHANNELS[ch_id]
            today = datetime.now().strftime('%Y년 %m월 %d일')
            prompt = f"""당신은 한국 유튜브 쇼츠 전문 작가입니다.
채널: {ch_info['name']} ({topic})
오늘 날짜: {today}
키워드: {keyword}

지시사항:
1. 60-90초 분량의 쇼츠 대본 작성
2. 첫 3초에 강력한 훅 포함
3. 자연스럽고 친근한 말투
4. AI 느낌 없이 실제 사람이 말하는 것처럼
5. 마지막에 구독/좋아요 유도

제목: (클릭하고 싶은 제목 1개)
---
대본: (실제 말할 내용)"""
            
            response = model.generate_content(prompt)
            text = response.text.strip()
            log.info(f"OK [{ch_info['name']}] Gemini 대본 생성 완료")
            return text
        except Exception as e:
            log.warning(f"WARN [{ch_id}] Gemini 오류: {e} → 기본 대본 사용")
    
    # Gemini 실패 or 키 없음 → 기본 대본
    scripts = DEFAULT_SCRIPTS.get(ch_id, DEFAULT_SCRIPTS['ch07'])
    script = random.choice(scripts)
    log.info(f"i [{ch_id}] 기본 대본 사용")
    return script

def generate_title_and_description(ch_id, script, hashtags):
    """제목, 설명, 해시태그 통합 생성"""
    ch_info = CHANNELS[ch_id]
    today = datetime.now().strftime('%m/%d')
    
    # 제목 추출 (대본에서 "제목:" 있으면 사용)
    title = None
    for line in script.split('\n'):
        if '제목:' in line or 'title:' in line.lower():
            title = line.replace('제목:', '').replace('Title:', '').strip()
            break
    
    if not title:
        # 기본 제목 패턴
        title_patterns = {
            'ch01': [f'오늘의 명언 {today} 🌟', f'마음을 울리는 한 마디 {today}', f'당신에게 필요한 말 {today}'],
            'ch02': [f'감성 무드 {today} 🎵', f'오늘의 플레이리스트 {today}', f'힐링 음악 모음 {today}'],
            'ch03': [f'오늘의 운동 {today} 💪', f'홈트 루틴 {today}', f'5분 스트레칭 {today}'],
            'ch04': [f'숙면 ASMR {today} 😴', f'오늘밤 수면 사운드 {today}', f'릴렉싱 백색소음 {today}'],
            'ch05': [f'귀여운 순간 {today} 🐾', f'오늘의 반려동물 {today}', f'힐링 동물영상 {today}'],
            'ch06': [f'솔직 리뷰 {today} ⭐', f'이번 주 꿀템 {today}', f'써보고 말하는 리뷰 {today}'],
            'ch07': [f'오늘의 이슈 {today} 🔥', f'알아야 할 정보 {today}', f'실시간 트렌드 {today}'],
            'ch08': [f'뷰티 꿀팁 {today} ✨', f'오늘의 스킨케어 {today}', f'뷰티 루틴 {today}'],
            'ch09': [f'오늘 뭐 먹을까 {today} 🍳', f'간단 레시피 {today}', f'맛집 정보 {today}'],
            'ch10': [f'이번 주 추천 {today} 🎬', f'꼭 봐야 할 영화 {today}', f'드라마 리뷰 {today}'],
            'ch11': [f'오늘의 코디 {today} 👗', f'데일리 룩 {today}', f'스타일 추천 {today}'],
            'ch12': [f'드라마 정보 {today} 📺', f'요즘 핫한 드라마 {today}', f'연예 이슈 {today}'],
        }
        patterns = title_patterns.get(ch_id, [f'오늘의 콘텐츠 {today}'])
        title = random.choice(patterns)
    
    # 설명 + 해시태그 구성
    tag_str = ' '.join(hashtags)
    description = f"""{script[:200]}...

📌 채널 구독하고 매일 새로운 콘텐츠 받아보세요!

{tag_str}

#쇼츠 #YouTubeShorts #슬다"""
    
    return title, description

# ─────────────────────────────────────────
# ⑤ TTS 음성 생성 (ElevenLabs → gTTS 폴백)
# ─────────────────────────────────────────
def generate_voice(text, ch_id):
    """ElevenLabs TTS, 실패시 gTTS"""
    voice_file = f'/tmp/voice_{ch_id}_{int(time.time())}.mp3'
    
    # ElevenLabs 시도
    if ELEVENLABS_KEY:
        try:
            voice_id = 'pNInz6obpgDQGcFmaJgB'  # Adam
            clean_text = re.sub(r'[#*\[\]{}]', '', text)[:500]
            
            resp = requests.post(
                f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
                headers={'xi-api-key': ELEVENLABS_KEY, 'Content-Type': 'application/json'},
                json={'text': clean_text, 'model_id': 'eleven_multilingual_v2',
                      'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}},
                timeout=30
            )
            if resp.status_code == 200:
                with open(voice_file, 'wb') as f:
                    f.write(resp.content)
                log.info(f"OK [{ch_id}] ElevenLabs 음성 완료 ({len(resp.content)//1024}KB)")
                return voice_file
            else:
                log.warning(f"WARN [{ch_id}] ElevenLabs 오류:{resp.status_code} → gTTS 폴백")
        except Exception as e:
            log.warning(f"WARN [{ch_id}] ElevenLabs 실패: {e}")
    
    # gTTS 폴백
    try:
        from gtts import gTTS
        clean_text = re.sub(r'[#*\[\]{}]', '', text)[:300]
        tts = gTTS(text=clean_text, lang='ko')
        tts.save(voice_file)
        log.info(f"OK [{ch_id}] gTTS 음성 완료")
        return voice_file
    except Exception as e:
        log.error(f"ERROR [{ch_id}] TTS 전체 실패: {e}")
        return None

# ─────────────────────────────────────────
# ⑥ Pexels 영상 가져오기
# ─────────────────────────────────────────
def get_pexels_video(keyword, ch_id):
    """Pexels에서 영상 다운로드"""
    if not PEXELS_KEY:
        log.error(f"ERROR [{ch_id}] Pexels 키 없음")
        return None
    
    try:
        queries = [keyword, keyword.split()[0], '자연 풍경']
        
        for query in queries:
            resp = requests.get(
                'https://api.pexels.com/videos/search',
                headers={'Authorization': PEXELS_KEY},
                params={'query': query, 'per_page': 15, 'orientation': 'portrait', 'size': 'medium'},
                timeout=15
            )
            if resp.status_code != 200:
                continue
            
            videos = resp.json().get('videos', [])
            if not videos:
                continue
            
            random.shuffle(videos)
            for vid in videos[:5]:
                files = vid.get('video_files', [])
                # HD 파일 선택
                hd_files = [f for f in files if f.get('quality') in ['hd', 'sd']]
                if hd_files:
                    target = hd_files[0]
                    dl_url = target['link']
                    
                    video_file = f'/tmp/pexels_{ch_id}_{int(time.time())}.mp4'
                    dl_resp = requests.get(dl_url, timeout=60, stream=True)
                    if dl_resp.status_code == 200:
                        with open(video_file, 'wb') as f:
                            for chunk in dl_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        size = os.path.getsize(video_file)
                        log.info(f"OK [{ch_id}] Pexels 다운로드: {size//1024}KB")
                        return video_file
        
        log.warning(f"WARN [{ch_id}] Pexels 영상 없음")
        return None
    except Exception as e:
        log.error(f"ERROR [{ch_id}] Pexels 오류: {e}")
        return None

# ─────────────────────────────────────────
# ⑦ AI 슬다 영상 합성 (ffmpeg)
# ─────────────────────────────────────────
def create_slda_video(ch_id, voice_file, video_file, title):
    """슬다 사진 + 영상 + 음성 합성"""
    output_file = f'/tmp/final_{ch_id}_{int(time.time())}.mp4'
    
    # 슬다 사진 URL (GitHub raw)
    slda_img_url = 'https://raw.githubusercontent.com/loveds887788778877-debug/slda-auto/main/slda.jpg'
    slda_img = '/tmp/slda_photo.jpg'
    
    if not os.path.exists(slda_img):
        try:
            r = requests.get(slda_img_url, timeout=15)
            if r.status_code == 200:
                with open(slda_img, 'wb') as f:
                    f.write(r.content)
                log.info("OK 슬다 사진 다운로드 완료")
        except Exception as e:
            log.warning(f"WARN 슬다 사진 다운로드 실패: {e}")
            slda_img = None
    
    try:
        if voice_file and video_file and os.path.exists(voice_file) and os.path.exists(video_file):
            # 음성 길이 확인
            probe = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', voice_file],
                capture_output=True, text=True
            )
            duration = 60  # 기본 60초
            try:
                probe_data = json.loads(probe.stdout)
                for stream in probe_data.get('streams', []):
                    if 'duration' in stream:
                        duration = float(stream['duration'])
                        break
            except:
                pass
            
            # ffmpeg: 영상 + 음성 합성 (슬다 워터마크 포함)
            if slda_img and os.path.exists(slda_img):
                cmd = [
                    'ffmpeg', '-y',
                    '-stream_loop', '-1', '-i', video_file,
                    '-i', voice_file,
                    '-i', slda_img,
                    '-filter_complex',
                    f'[2:v]scale=120:120,geq=lum=\'p(X,Y)\':cb=\'p(X,Y)\':cr=\'p(X,Y)\',format=yuva420p,colorchannelmixer=aa=0.8[slda];'
                    f'[0:v]scale=1080:1920,setsar=1[bg];'
                    f'[bg][slda]overlay=main_w-overlay_w-20:20[v]',
                    '-map', '[v]', '-map', '1:a',
                    '-t', str(min(duration, 60)),
                    '-c:v', 'libx264', '-c:a', 'aac',
                    '-preset', 'ultrafast', '-crf', '28',
                    output_file
                ]
            else:
                cmd = [
                    'ffmpeg', '-y',
                    '-stream_loop', '-1', '-i', video_file,
                    '-i', voice_file,
                    '-t', str(min(duration, 60)),
                    '-c:v', 'libx264', '-c:a', 'aac',
                    '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
                    '-preset', 'ultrafast', '-crf', '28',
                    output_file
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and os.path.exists(output_file):
                size = os.path.getsize(output_file)
                log.info(f"OK [{ch_id}] 영상 합성 완료 ({size//1024}KB)")
                return output_file
            else:
                log.error(f"ERROR [{ch_id}] ffmpeg 실패: {result.stderr[-200:]}")
        
        # 음성만 있는 경우 → 슬다 사진으로 슬라이드쇼
        if voice_file and slda_img and os.path.exists(voice_file) and os.path.exists(slda_img):
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', slda_img,
                '-i', voice_file,
                '-c:v', 'libx264', '-c:a', 'aac',
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
                '-shortest', '-preset', 'ultrafast',
                output_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                log.info(f"OK [{ch_id}] 슬다 사진 영상 합성 완료")
                return output_file
    
    except Exception as e:
        log.error(f"ERROR [{ch_id}] 영상 합성 오류: {e}")
    
    # 최후 폴백: 원본 영상 그대로 반환
    return video_file if video_file and os.path.exists(video_file) else None

# ─────────────────────────────────────────
# ⑧ YouTube 업로드
# ─────────────────────────────────────────
TOKEN_DIR = '/app/tokens'

def upload_to_youtube(ch_id, video_file, title, description):
    """YouTube API로 업로드"""
    token_path = os.path.join(TOKEN_DIR, f'{ch_id}_token.pickle')
    
    if not os.path.exists(token_path):
        log.warning(f"WARN [{ch_id}] 토큰 없음: {token_path}")
        return None, f'토큰 없음 ({ch_id})'
    
    if not video_file or not os.path.exists(video_file):
        log.error(f"ERROR [{ch_id}] 영상 파일 없음")
        return None, '영상 파일 없음'
    
    try:
        with open(token_path, 'rb') as f:
            creds_data = pickle.load(f)
        
        if isinstance(creds_data, dict):
            creds = Credentials(
                token=creds_data.get('token'),
                refresh_token=creds_data.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=creds_data.get('client_id'),
                client_secret=creds_data.get('client_secret'),
                scopes=creds_data.get('scopes', ['https://www.googleapis.com/auth/youtube.upload'])
            )
        else:
            creds = creds_data
        
        youtube = build('youtube', 'v3', credentials=creds)
        
        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000],
                'tags': ['슬다', '쇼츠', 'shorts'],
                'categoryId': '22',
                'defaultLanguage': 'ko'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }
        
        media = MediaFileUpload(video_file, mimetype='video/mp4', resumable=True, chunksize=1024*1024)
        request_yt = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request_yt.next_chunk()
        
        video_id = response.get('id', '')
        url = f'https://youtube.com/shorts/{video_id}'
        log.info(f"OK [{ch_id}] ✅ 업로드 완료! {url}")
        return video_id, url
    
    except Exception as e:
        log.error(f"ERROR [{ch_id}] YouTube 업로드 실패: {e}")
        return None, str(e)

# ─────────────────────────────────────────
# ⑨ 채널별 자동 실행 파이프라인
# ─────────────────────────────────────────
upload_log = []
pipeline_running = False

def run_channel(ch_id):
    """단일 채널 완전 자동화 실행"""
    ch_info = CHANNELS.get(ch_id)
    if not ch_info:
        return
    
    name = ch_info['name']
    topic = ch_info['topic']
    keyword = ch_info['keyword']
    
    log.info(f"i [1/5] {name} 시작")
    result = {'ch_id': ch_id, 'name': name, 'time': datetime.now().strftime('%H:%M:%S'),
              'status': '진행중', 'url': '', 'error': ''}
    
    try:
        # 1. 대본 생성
        script = generate_script(ch_id, topic, keyword)
        
        # 2. 해시태그 10개 (오늘 날짜 기반)
        hashtags = get_trending_hashtags(ch_id)
        
        # 3. 제목 + 설명
        title, description = generate_title_and_description(ch_id, script, hashtags)
        log.info(f"i [{name}] 제목: {title}")
        
        # 4. 음성 생성
        voice_file = generate_voice(script[:500], ch_id)
        
        # 5. 영상 가져오기 (Pexels)
        video_file = get_pexels_video(keyword, ch_id)
        
        # 6. 영상 합성
        final_video = create_slda_video(ch_id, voice_file, video_file, title)
        
        # 7. YouTube 업로드
        if final_video:
            vid_id, url = upload_to_youtube(ch_id, final_video, title, description)
            if vid_id:
                result['status'] = '완료'
                result['url'] = url
                result['title'] = title
                result['hashtags'] = hashtags
            else:
                result['status'] = '업로드실패'
                result['error'] = url
        else:
            result['status'] = '영상없음'
        
        # 임시 파일 정리
        for f in [voice_file, video_file, final_video]:
            if f and f != video_file and os.path.exists(f) and '/tmp/' in f:
                try:
                    os.remove(f)
                except:
                    pass
    
    except Exception as e:
        result['status'] = '오류'
        result['error'] = str(e)
        log.error(f"ERROR [{name}] 파이프라인 오류: {e}")
    
    upload_log.append(result)
    if len(upload_log) > 200:
        upload_log.pop(0)
    
    return result

def run_all_channels():
    """12채널 전체 자동 실행"""
    global pipeline_running
    if pipeline_running:
        log.warning("WARN 이미 실행 중 - 스킵")
        return
    
    pipeline_running = True
    log.info(f"🚀 자동 업로드 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    for ch_id in CHANNELS.keys():
        try:
            run_channel(ch_id)
            time.sleep(5)  # 채널간 딜레이
        except Exception as e:
            log.error(f"ERROR {ch_id}: {e}")
    
    pipeline_running = False
    log.info("✅ 전체 채널 업로드 완료")

# ─────────────────────────────────────────
# ⑩ 스케줄러 (09:00 / 13:00 / 19:00)
# ─────────────────────────────────────────
def start_scheduler():
    schedule.every().day.at("09:00").do(lambda: threading.Thread(target=run_all_channels, daemon=True).start())
    schedule.every().day.at("13:00").do(lambda: threading.Thread(target=run_all_channels, daemon=True).start())
    schedule.every().day.at("19:00").do(lambda: threading.Thread(target=run_all_channels, daemon=True).start())
    
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─────────────────────────────────────────
# ⑪ 웹 대시보드
# ─────────────────────────────────────────
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>슬다 자동화 v15.5</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Apple SD Gothic Neo','맑은 고딕',sans-serif; background:#0a0a0f; color:#e0e0e0; }
.header { background:linear-gradient(135deg,#1a0a2e,#16213e); padding:20px; text-align:center; border-bottom:2px solid #7c3aed; }
.header h1 { font-size:1.8em; color:#c084fc; font-weight:800; }
.header .sub { color:#94a3b8; font-size:0.85em; margin-top:5px; }
.status-bar { display:flex; gap:15px; padding:15px 20px; background:#111; flex-wrap:wrap; }
.status-pill { padding:6px 14px; border-radius:20px; font-size:0.78em; font-weight:600; }
.pill-green { background:#14532d; color:#4ade80; border:1px solid #4ade80; }
.pill-red { background:#450a0a; color:#f87171; border:1px solid #f87171; }
.pill-yellow { background:#422006; color:#fbbf24; border:1px solid #fbbf24; }
.container { padding:20px; max-width:1200px; margin:0 auto; }
.section-title { font-size:1em; color:#7c3aed; font-weight:700; margin:20px 0 10px; text-transform:uppercase; letter-spacing:1px; }
.btn-row { display:flex; gap:10px; margin-bottom:20px; flex-wrap:wrap; }
.btn { padding:10px 20px; border:none; border-radius:8px; cursor:pointer; font-size:0.9em; font-weight:600; transition:all 0.2s; }
.btn-primary { background:#7c3aed; color:white; }
.btn-primary:hover { background:#6d28d9; transform:translateY(-1px); }
.btn-success { background:#059669; color:white; }
.btn-success:hover { background:#047857; }
.btn-info { background:#0284c7; color:white; }
.btn-info:hover { background:#0369a1; }
.channels-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }
.channel-card { background:#111827; border:1px solid #1f2937; border-radius:10px; padding:14px; }
.channel-card.ok { border-color:#065f46; }
.channel-card.error { border-color:#7f1d1d; }
.channel-name { font-weight:700; font-size:0.95em; margin-bottom:8px; }
.channel-tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:8px; }
.tag { background:#1e1b4b; color:#a5b4fc; padding:2px 8px; border-radius:10px; font-size:0.7em; }
.channel-url { color:#60a5fa; font-size:0.75em; word-break:break-all; margin-top:6px; }
.log-box { background:#0d1117; border:1px solid #21262d; border-radius:10px; padding:15px; height:300px; overflow-y:auto; font-family:'Courier New',monospace; font-size:0.78em; }
.log-ok { color:#4ade80; }
.log-warn { color:#fbbf24; }
.log-err { color:#f87171; }
.log-info { color:#93c5fd; }
.hashtag-preview { background:#111827; border:1px solid #1f2937; border-radius:10px; padding:15px; margin-top:10px; }
.ht-channel { margin-bottom:15px; }
.ht-name { color:#c084fc; font-weight:700; font-size:0.85em; margin-bottom:8px; }
.ht-tags { display:flex; flex-wrap:wrap; gap:5px; }
.ht-tag { background:#312e81; color:#a5b4fc; padding:3px 10px; border-radius:12px; font-size:0.75em; }
.progress-bar { background:#1f2937; border-radius:4px; height:6px; margin-top:8px; }
.progress-fill { height:100%; border-radius:4px; background:linear-gradient(90deg,#7c3aed,#ec4899); transition:width 0.5s; }
</style>
</head>
<body>
<div class="header">
  <h1>🌸 슬다 자동화 v15.5</h1>
  <div class="sub">Gemini 1.5 flash · ElevenLabs · Pexels · YouTube 자동 업로드</div>
</div>

<div class="status-bar" id="statusBar">
  <span class="status-pill pill-yellow" id="geminiStatus">Gemini: 확인 중...</span>
  <span class="status-pill pill-yellow" id="pexelsStatus">Pexels: 확인 중...</span>
  <span class="status-pill pill-yellow" id="elevenStatus">ElevenLabs: 확인 중...</span>
  <span class="status-pill pill-yellow" id="scheduleStatus">스케줄: 09:00 / 13:00 / 19:00</span>
</div>

<div class="container">
  <div class="section-title">🎮 제어판</div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="runAll()">🚀 전체 실행 (12채널)</button>
    <button class="btn btn-success" onclick="runSingle()">▶ 테스트 (ch01만)</button>
    <button class="btn btn-info" onclick="loadHashtags()">🏷️ 오늘의 해시태그 확인</button>
    <button class="btn" style="background:#374151;color:#e5e7eb" onclick="clearLog()">🗑️ 로그 초기화</button>
  </div>

  <div class="section-title">🏷️ 오늘의 채널별 해시태그 10개</div>
  <div class="hashtag-preview" id="hashtagPreview">
    <div style="color:#6b7280;text-align:center;padding:20px;">위의 '해시태그 확인' 버튼을 눌러주세요</div>
  </div>

  <div class="section-title">📺 채널 업로드 현황</div>
  <div class="channels-grid" id="channelsGrid"></div>

  <div class="section-title" style="margin-top:20px;">📋 실행 로그</div>
  <div class="log-box" id="logBox"></div>
</div>

<script>
const CHANNELS = {
  ch01:'한줄의린',ch02:'무드웨이브',ch03:'피트노트',ch04:'딥슬립룸',
  ch05:'몽글클럽',ch06:'픽앤리뷰',ch07:'이슈타르',ch08:'뷰티끄',
  ch09:'한끼스케치',ch10:'무비착',ch11:'룩북노트',ch12:'드라마찜'
};

let logInterval, statusInterval;

async function fetchStatus() {
  try {
    const r = await fetch('/status');
    const d = await r.json();
    
    document.getElementById('geminiStatus').textContent = `Gemini: ${d.gemini_keys}개`;
    document.getElementById('geminiStatus').className = `status-pill ${d.gemini_keys > 0 ? 'pill-green' : 'pill-red'}`;
    
    document.getElementById('pexelsStatus').textContent = `Pexels: ${d.pexels ? '연결됨' : '오류'}`;
    document.getElementById('pexelsStatus').className = `status-pill ${d.pexels ? 'pill-green' : 'pill-red'}`;
    
    document.getElementById('elevenStatus').textContent = `ElevenLabs: ${d.elevenlabs ? '연결됨' : 'gTTS폴백'}`;
    document.getElementById('elevenStatus').className = `status-pill ${d.elevenlabs ? 'pill-green' : 'pill-yellow'}`;
  } catch(e) {}
}

async function fetchLogs() {
  try {
    const r = await fetch('/logs');
    const d = await r.json();
    const box = document.getElementById('logBox');
    
    // 채널 카드 업데이트
    updateChannelCards(d.results || []);
    
    // 로그 표시
    const lines = (d.logs || []).slice(-50);
    box.innerHTML = lines.map(line => {
      let cls = 'log-info';
      if(line.includes('ERROR') || line.includes('오류')) cls = 'log-err';
      else if(line.includes('WARN')) cls = 'log-warn';
      else if(line.includes('OK') || line.includes('완료') || line.includes('✅')) cls = 'log-ok';
      return `<div class="${cls}">${line}</div>`;
    }).join('');
    box.scrollTop = box.scrollHeight;
  } catch(e) {}
}

function updateChannelCards(results) {
  const grid = document.getElementById('channelsGrid');
  let html = '';
  for(const [chId, name] of Object.entries(CHANNELS)) {
    const r = results.find(x => x.ch_id === chId) || {};
    const ok = r.status === '완료';
    html += `<div class="channel-card ${ok ? 'ok' : (r.status ? 'error' : '')}">
      <div class="channel-name">${name} <span style="color:#6b7280;font-size:0.75em">${chId}</span></div>
      <div style="font-size:0.8em;color:${ok?'#4ade80':r.status?'#f87171':'#6b7280'}">${r.status || '대기중'}</div>
      ${r.title ? `<div style="font-size:0.75em;color:#94a3b8;margin-top:4px">${r.title}</div>` : ''}
      ${r.hashtags ? `<div class="channel-tags">${r.hashtags.slice(0,5).map(t=>`<span class="tag">${t}</span>`).join('')}</div>` : ''}
      ${r.url ? `<div class="channel-url"><a href="${r.url}" target="_blank">${r.url}</a></div>` : ''}
    </div>`;
  }
  grid.innerHTML = html;
}

async function loadHashtags() {
  try {
    const r = await fetch('/hashtags');
    const d = await r.json();
    const preview = document.getElementById('hashtagPreview');
    
    let html = '';
    for(const [chId, data] of Object.entries(d)) {
      html += `<div class="ht-channel">
        <div class="ht-name">📺 ${data.name}</div>
        <div class="ht-tags">${data.tags.map(t=>`<span class="ht-tag">${t}</span>`).join('')}</div>
      </div>`;
    }
    preview.innerHTML = html;
  } catch(e) { alert('해시태그 로드 오류: ' + e); }
}

async function runAll() {
  if(!confirm('12채널 전체 업로드를 시작할까요? (시간이 걸립니다)')) return;
  fetch('/run_all', {method:'POST'});
  appendLog('🚀 전체 실행 요청됨...');
}

async function runSingle() {
  fetch('/run_single/ch01', {method:'POST'});
  appendLog('▶ ch01 테스트 실행 중...');
}

function appendLog(msg) {
  const box = document.getElementById('logBox');
  box.innerHTML += `<div class="log-info">[${new Date().toTimeString().slice(0,8)}] ${msg}</div>`;
  box.scrollTop = box.scrollHeight;
}

function clearLog() {
  fetch('/clear_log', {method:'POST'});
  document.getElementById('logBox').innerHTML = '';
}

// 초기화
fetchStatus();
fetchLogs();
statusInterval = setInterval(fetchStatus, 30000);
logInterval = setInterval(fetchLogs, 5000);
</script>
</body>
</html>'''

# ─────────────────────────────────────────
# ⑫ Flask 라우트
# ─────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/status')
def status():
    return jsonify({
        'gemini_keys': len(GEMINI_KEYS),
        'pexels': bool(PEXELS_KEY),
        'elevenlabs': bool(ELEVENLABS_KEY),
        'kling': bool(KLING_KEY),
        'pipeline_running': pipeline_running,
        'channels': len(CHANNELS)
    })

@app.route('/logs')
def get_logs():
    return jsonify({
        'results': upload_log,
        'logs': [r.get('name','') + ' ' + r.get('status','') + ' ' + r.get('url','') 
                 for r in upload_log[-50:]]
    })

@app.route('/hashtags')
def get_hashtags():
    result = {}
    for ch_id, ch_info in CHANNELS.items():
        tags = get_trending_hashtags(ch_id)
        result[ch_id] = {'name': ch_info['name'], 'tags': tags}
    return jsonify(result)

@app.route('/run_all', methods=['POST'])
def api_run_all():
    threading.Thread(target=run_all_channels, daemon=True).start()
    return jsonify({'status': 'started'})

@app.route('/run_single/<ch_id>', methods=['POST'])
def api_run_single(ch_id):
    threading.Thread(target=run_channel, args=(ch_id,), daemon=True).start()
    return jsonify({'status': 'started', 'ch_id': ch_id})

@app.route('/clear_log', methods=['POST'])
def api_clear_log():
    upload_log.clear()
    return jsonify({'status': 'cleared'})

# ─────────────────────────────────────────
# ⑬ 메인 진입점
# ─────────────────────────────────────────
if __name__ == '__main__':
    log.info("=" * 50)
    log.info("🌸 슬다 자동화 v15.5 시작")
    log.info(f"OK Gemini 키: {len(GEMINI_KEYS)}개")
    log.info(f"{'OK' if PEXELS_KEY else 'WARN'} Pexels: {'연결됨' if PEXELS_KEY else '없음'}")
    log.info(f"{'OK' if ELEVENLABS_KEY else 'WARN'} ElevenLabs: {'연결됨' if ELEVENLABS_KEY else 'gTTS폴백'}")
    log.info(f"OK 채널: {len(CHANNELS)}개 자동화")
    log.info("OK 스케줄: 09:00 / 13:00 / 19:00")
    log.info("=" * 50)
    
    # 스케줄러 백그라운드 시작
    threading.Thread(target=start_scheduler, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
