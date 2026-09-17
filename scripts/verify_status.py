import os
import sys
import json
import yt_dlp
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

# .env 로드
load_dotenv()

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            msg = " ".join(str(a) for a in args)
            sys.stdout.buffer.write((msg + "\n").encode('utf-8', errors='replace'))
        except Exception:
            pass

def send_alert_email(error_details):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()
    
    # 수신자 고정
    receiver_email = "rmmi201209@gmail.com"
    
    sender_password = sender_password.replace(" ", "")
    
    if not sender_email or not sender_password:
        safe_print("[ERROR] .env 파일에 이메일 설정이 누락되어 경고 메일을 보낼 수 없습니다.")
        return

    subject = "[경고] 유튜브 요약 자동화 파이프라인 오류 알림"
    body = f"""유튜브 요약 파이프라인 검증 중 문제가 발생했습니다.
아래 상세 내역을 확인해 주세요.

{error_details}
    """

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        safe_print(f"[INFO] 에러 알림 메일이 {receiver_email}로 성공적으로 발송되었습니다.")
    except Exception as e:
        safe_print(f"[ERROR] 에러 알림 메일 발송 실패: {e}")

def verify_system_status():
    safe_print("="*50)
    safe_print("유튜브 요약 자동화 시스템 상태 검증을 시작합니다...")
    safe_print("="*50)

    # 1. 채널 정보 로드
    channels_path = os.path.abspath("channels.json")
    if not os.path.exists(channels_path):
        safe_print("[ERROR] channels.json 파일을 찾을 수 없습니다.")
        return
    with open(channels_path, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # 2. 데이터베이스 로드
    data_path = os.path.abspath(os.path.join("public", "data.json"))
    if not os.path.exists(data_path):
        safe_print("[ERROR] public/data.json 파일을 찾을 수 없습니다.")
        data_list = []
    else:
        with open(data_path, "r", encoding="utf-8") as f:
            data_list = json.load(f)
    
    existing_records = {item.get("id"): item for item in data_list if item.get("id")}

    from googleapiclient.discovery import build
    
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        safe_print("[ERROR] YOUTUBE_API_KEY가 설정되지 않아 상태 검증을 수행할 수 없습니다.")
        return
        
    youtube = build("youtube", "v3", developerKey=youtube_api_key)
    all_good = True
    error_messages = []
    
    for ch in channels:
        ch_name = ch["name"]
        ch_id = ch["id"]
        
        try:
            uploads_playlist_id = "UU" + ch_id[2:]
            playlist_response = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=1
            ).execute()
            
            if not playlist_response.get("items"):
                msg = f"[{ch_name}] 최신 영상을 가져올 수 없습니다."
                safe_print(msg)
                error_messages.append(msg)
                all_good = False
                continue
            
            latest_video = playlist_response["items"][0]
            video_id = latest_video["snippet"]["resourceId"]["videoId"]
            title = latest_video["snippet"]["title"]
            
            safe_print(f"\n▶ 채널: {ch_name}")
            safe_print(f"  - 최신 영상: {title} ({video_id})")
            
            record = existing_records.get(video_id)
            if record:
                summary_exists = bool(record.get("summary"))
                email_sent = record.get("email_sent", False)
                
                status_summary = "✅ 성공" if summary_exists else "❌ 실패"
                status_email = "✅ 발송완료" if email_sent else "❌ 미발송"
                
                safe_print(f"  - 요약 생성: {status_summary}")
                safe_print(f"  - 메일 발송: {status_email}")
                
                if not summary_exists or not email_sent:
                    all_good = False
                    error_messages.append(f"[{ch_name}] {title}\n  - 요약 생성: {status_summary}\n  - 메일 발송: {status_email}")
            else:
                safe_print(f"  - 데이터베이스 상태: ❌ 누락됨 (아직 감지되지 않았거나 파이프라인 미실행)")
                all_good = False
                error_messages.append(f"[{ch_name}] {title}\n  - 데이터베이스 상태: ❌ 누락됨")
                
        except Exception as e:
            msg = f"[ERROR] {ch_name} 정보 추출 중 오류 발생: {e}"
            safe_print(msg)
            error_messages.append(msg)
            all_good = False

    safe_print("\n" + "="*50)
    if all_good:
        safe_print("🎉 모든 채널의 최신 영상이 정상적으로 요약 및 메일 발송되었습니다!")
    else:
        safe_print("⚠️ 일부 채널의 최신 영상 처리가 누락되었거나 실패했습니다. 수동 확인이 필요합니다.")
        safe_print("   (방금 올라온 영상일 경우 다음 스케줄러 실행 시 처리됩니다.)")
        
        # 에러 내역을 정리하여 이메일 발송
        error_details = "\n\n".join(error_messages)
        send_alert_email(error_details)
        
    safe_print("="*50)

if __name__ == "__main__":
    verify_system_status()
