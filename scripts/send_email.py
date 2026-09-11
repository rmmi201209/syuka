import os
import sys
import json
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def send_summary_email(force=False):
    """
    public/data.json에서 가장 최신 요약을 읽어와 이메일로 전송합니다.
    방금 생성된 요약(10분 이내)이거나 force=True일 때만 전송합니다.
    """
    data_path = os.path.abspath(os.path.join("public", "data.json"))
    
    if not os.path.exists(data_path):
        print("[ERROR] Database file public/data.json not found. Cannot send email.")
        return False
        
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read database file: {e}")
        return False
        
    if not data:
        print("[INFO] Database is empty. No summary to email.")
        return False
        
    # 가장 최신 요약본 (배열의 맨 앞)
    latest_item = data[0]
    video_id = latest_item.get("id")
    title = latest_item.get("title")
    published = latest_item.get("published")
    summary = latest_item.get("summary")
    created_at_str = latest_item.get("created_at")
    
    if not summary:
        print("[ERROR] Latest item does not contain summary data.")
        return False

    # 시간 체크 (최근 10분 이내에 생성된 항목인지 검사)
    if not force and created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str)
            now = datetime.now(timezone.utc)
            time_diff = now - created_at
            
            # 10분(600초) 이상 지난 항목이면 메일을 발송하지 않음
            if time_diff.total_seconds() > 600:
                print(f"[INFO] Latest summary for '{title}' was created {time_diff.total_seconds()/60:.1f} minutes ago. Skipping email send (no new upload).")
                return True
        except Exception as e:
            print(f"[WARNING] Time comparison failed, skipping email check: {e}")
            
    # 환경변수 로드
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()
    receiver_email = os.getenv("RECEIVER_EMAIL", "").strip()
    
    # 띄어쓰기 공백 제거 (앱 비밀번호의 4자리 단위 띄어쓰기 제거)
    sender_password = sender_password.replace(" ", "")
    
    if not sender_email or not sender_password or not receiver_email:
        print("[ERROR] Email SMTP configuration missing in .env file (SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL).")
        print("[INFO] If this is running in GitHub Actions, make sure to set these in GitHub Secrets.")
        return False

    if sender_email == "your_gmail_username@gmail.com":
        print("[ERROR] Default placeholder values found in .env. Please configure SMTP variables.")
        return False

    print(f"[INFO] Preparing email for video: {title}")

    # HTML 메일 템플릿 작성
    # 주제별로 챕터 목록을 HTML 문자열로 가공
    chapters_html = ""
    for ch in summary.get("chapters", []):
        chapters_html += f"""
        <div style="margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #EAEAEA;">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #4F46E5; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; margin-right: 10px;">
                    {ch.get('timeline', '00:00')}
                </span>
                <h3 style="margin: 0; color: #1E1B4B; font-size: 16px; font-weight: 700;">
                    {ch.get('title', '주제')}
                </h3>
            </div>
            <p style="margin: 0; color: #4B5563; font-size: 14px; line-height: 1.6; white-space: pre-line;">
                {ch.get('content', '')}
            </p>
        </div>
        """

    # 키워드 뱃지 HTML 가공
    keywords_html = ""
    for kw in summary.get("keywords", []):
        keywords_html += f"""
        <span style="display: inline-block; background-color: #EEF2F6; color: #4F46E5; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 12px; margin-right: 6px; margin-bottom: 6px;">
            #{kw}
        </span>
        """

    # 전체 HTML 이메일 본문 조립
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>[슈카월드] 오늘의 요약 브리핑</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" max-width="600" style="max-width: 600px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #E5E7EB;">
            <!-- 헤더 그라디언트 영역 -->
            <tr>
                <td style="background: linear-gradient(135deg, #1E1B4B 0%, #4F46E5 100%); padding: 30px; text-align: center;">
                    <span style="color: #A5B4FC; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1.5px;">DAILY SUMMARY NEWSLETTER</span>
                    <h1 style="margin: 10px 0 0 0; color: #FFFFFF; font-size: 24px; font-weight: 800;">슈카월드 핵심 브리핑</h1>
                    <p style="margin: 5px 0 0 0; color: #C7D2FE; font-size: 13px;">오전 5시 자동 업로드 감지 시스템</p>
                </td>
            </tr>
            <!-- 본문 영역 -->
            <tr>
                <td style="padding: 30px;">
                    <!-- 제목 및 링크 -->
                    <div style="margin-bottom: 25px;">
                        <h2 style="margin: 0 0 8px 0; color: #111827; font-size: 18px; font-weight: 800; line-height: 1.4;">
                            {title}
                        </h2>
                        <a href="https://www.youtube.com/watch?v={video_id}" target="_blank" style="display: inline-block; color: #4F46E5; font-size: 13px; font-weight: bold; text-decoration: none;">
                            📺 유튜브에서 영상 보기 &rarr;
                        </a>
                    </div>
                    
                    <!-- 한줄 요약 -->
                    <div style="background-color: #EEF2F6; border-left: 4px solid #4F46E5; padding: 15px; border-radius: 4px 8px 8px 4px; margin-bottom: 25px;">
                        <p style="margin: 0; color: #1E1B4B; font-weight: 700; font-size: 14px; line-height: 1.5;">
                            💡 {summary.get('one_liner', '')}
                        </p>
                    </div>

                    <!-- 키워드 영역 -->
                    <div style="margin-bottom: 30px;">
                        {keywords_html}
                    </div>

                    <!-- 구분선 -->
                    <hr style="border: 0; border-top: 1px solid #E5E7EB; margin-bottom: 25px;">

                    <!-- 세부 챕터 요약 -->
                    <div>
                        <h4 style="margin: 0 0 20px 0; color: #4F46E5; font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">주요 내용 요약</h4>
                        {chapters_html}
                    </div>

                    <!-- 에디터 인사이트 -->
                    <div style="background-color: #F9FAFB; border: 1px solid #F3F4F6; border-radius: 12px; padding: 20px; margin-top: 15px;">
                        <h4 style="margin: 0 0 10px 0; color: #1E1B4B; font-size: 14px; font-weight: 800;">🔑 핵심 인사이트 & 총평</h4>
                        <p style="margin: 0; color: #4B5563; font-size: 13.5px; line-height: 1.6; white-space: pre-line;">
                            {summary.get('insights', '')}
                        </p>
                    </div>
                </td>
            </tr>
            <!-- 푸터 영역 -->
            <tr>
                <td style="background-color: #F9FAFB; padding: 20px; text-align: center; border-top: 1px solid #E5E7EB;">
                    <p style="margin: 0; color: #9CA3AF; font-size: 12px;">본 메일은 매일 오전 5시 슈카월드 유튜브 채널의 신규 동영상을 감지하여 발송되는 자동화 메일입니다.</p>
                    <p style="margin: 5px 0 0 0; color: #9CA3AF; font-size: 11px;">&copy; {datetime.now().year} 슈카월드 요약 봇. All rights reserved.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    from email.header import Header

    # 이메일 메시지 생성
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"[슈카월드 요약] {title}", "utf-8")
    msg["From"] = sender_email
    msg["To"] = receiver_email
    
    # HTML 본문 추가 (utf-8 명시)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        # SMTP 서버 연결 및 메일 발송
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls() # TLS 보안 연결 설정
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"[SUCCESS] Email successfully sent to {receiver_email} for video: {title}")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Failed to send email: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Syuka World Summary Email")
    parser.add_argument("--force", action="store_true", help="Send email ignoring 10-minute creation window limit")
    args = parser.parse_args()
    
    success = send_summary_email(force=args.force)
    if not success:
        sys.exit(1)
