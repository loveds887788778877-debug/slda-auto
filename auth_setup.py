"""
슬다 채널 인증 v10 - 쉽게 한 번에!
실행: python auth_setup.py
"""
import os, pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR   = Path(r"C:\Users\MYCOM\Desktop\제코자동화")
SECRET     = BASE_DIR / "client_secret.json"
TOKENS_DIR = BASE_DIR / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CHANNELS = {
    "ch01":"한줄의 린","ch02":"무드웨이브","ch03":"피트노트",
    "ch04":"딥슬립룸","ch05":"몽글클럽","ch06":"픽앤리뷰",
    "ch07":"이슈타르","ch08":"뷰티끄","ch09":"한끼스케치",
    "ch10":"무비착","ch11":"룩북노트","ch12":"드라마찜",
    "ch13":"트래블로그","ch14":"퀴즈는","ch15":"밈스토리",
}

def auth_channel(ch_id, name):
    path = TOKENS_DIR / f"token_{ch_id}.pickle"
    creds = None
    if path.exists():
        with open(path,"rb") as f: creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        print(f"\n  👉 [{name}] 계정으로 로그인하세요!")
        flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        with open(path,"wb") as f: pickle.dump(creds, f)
    try:
        svc = build("youtube","v3",credentials=creds)
        r = svc.channels().list(part="snippet",mine=True).execute()
        title = r["items"][0]["snippet"]["title"] if r.get("items") else "채널없음"
        print(f"  ✅ [{name}] 인증완료 → {title}")
        return True
    except Exception as e:
        print(f"  ❌ [{name}] 오류: {e}")
        return False

def main():
    print("="*50)
    print("  슬다 채널 인증 v10")
    print("="*50)

    if not SECRET.exists():
        print(f"""
❌ client_secret.json 파일이 없어요!

📌 만드는 법:
  1. console.cloud.google.com 접속
  2. 새 프로젝트 만들기 (이름: SLDA)
  3. API 및 서비스 → 라이브러리
  4. YouTube Data API v3 → 사용 설정
  5. 사용자 인증 정보 → OAuth 2.0 클라이언트 ID
  6. 애플리케이션 유형: 데스크톱 앱
  7. JSON 다운로드 → 이름을 client_secret.json 으로 변경
  8. {SECRET} 에 저장

완료 후 다시 실행하세요!
""")
        return

    print("\n어떤 채널 인증할까요?")
    print("  0 = 전체 (15개)")
    for ch_id, name in CHANNELS.items():
        exists = "✅" if (TOKENS_DIR/f"token_{ch_id}.pickle").exists() else "⬜"
        print(f"  {ch_id[-2:]} = {name} {exists}")

    choice = input("\n번호 입력 (예: 01  또는  0=전체): ").strip()

    if choice == "0":
        targets = list(CHANNELS.keys())
    elif f"ch{choice.zfill(2)}" in CHANNELS:
        targets = [f"ch{choice.zfill(2)}"]
    else:
        print("❌ 잘못된 입력"); return

    success = sum(auth_channel(cid, CHANNELS[cid]) for cid in targets)
    print(f"\n🎉 완료! {success}/{len(targets)}개 인증됨")
    print("이제 python app.py 실행하면 돼요!\n")

if __name__ == "__main__":
    main()
