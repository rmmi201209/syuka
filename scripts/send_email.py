import os
import sys
import json
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timezone
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            msg = " ".join(str(a) for a in args)
            sys.stdout.buffer.write((msg + "\n").encode('utf-8', errors='replace'))
        except Exception:
            pass

# .env 파일 로드
load_dotenv()

def send_individual_email(server, sender_email, receiver_email, item):
    video_id = item.get("id")
    title = item.get("title", "유튜브 영상 요약")
    channel_name = item.get("channel_name", "경제 브리핑")
    badge_color = item.get("badge_color", "#4F46E5")
    summary = item.get("summary", {})

    subject_str = f"[{channel_name}] {title}"

    # 챕터 목록 HTML
    chapters_html = ""
    for ch in summary.get("chapters", []):
        chapters_html += f"""
        <div style="margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px dashed #E5E7EB;">
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="background-color: {badge_color}; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; margin-right: 10px;">
                    {ch.get('timeline', '00:00')}
                </span>
                <strong style="color: #1E1B4B; font-size: 15.5px;">
                    {ch.get('title', '주제')}
                </strong>
            </div>
            <p style="margin: 0; color: #4B5563; font-size: 14px; line-height: 1.65; white-space: pre-line;">
                {ch.get('content', '')}
            </p>
        </div>
        """

    # 키워드 뱃지 HTML
    keywords_html = ""
    for kw in summary.get("keywords", []):
        keywords_html += f"""
        <span style="display: inline-block; background-color: #F3F4F6; color: {badge_color}; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 12px; margin-right: 6px; margin-bottom: 6px;">
            #{kw}
        </span>
        """

    # 개별 단일 영상 전용 HTML 뉴스레터 템플릿
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>[{channel_name}] {title}</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" max-width="640" style="max-width: 640px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; overflow: hidden; border: 1px solid #E5E7EB; box-shadow: 0 4px 12px rgba(0,0,0,0.04);">
            <!-- 채널 맞춤형 헤더 그라데이션 -->
            <tr>
                <td style="background: linear-gradient(135deg, #0F172A 0%, {badge_color} 100%); padding: 32px 28px; text-align: center;">
                    <span style="color: #FFFFFF; opacity: 0.85; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px;">
                        {channel_name} · AI SUMMARY
                    </span>
                    <h1 style="margin: 10px 0 0 0; color: #FFFFFF; font-size: 22px; font-weight: 800; line-height: 1.35;">
                        {title}
                    </h1>
                </td>
            </tr>
            <!-- 본문 콘텐츠 -->
            <tr>
                <td style="padding: 28px;">
                    <!-- 바로가기 버튼 -->
                    <div style="text-align: center; margin-bottom: 24px;">
                        <a href="https://www.youtube.com/watch?v={video_id}" target="_blank" style="display: inline-block; background-color: {badge_color}; color: #FFFFFF; font-size: 13.5px; font-weight: bold; text-decoration: none; padding: 10px 20px; border-radius: 25px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                            ▶ YouTube에서 영상 보기 &rarr;
                        </a>
                    </div>

                    <!-- 강렬한 한 줄 요약 -->
                    <div style="background-color: #F8FAFC; border-left: 4px solid {badge_color}; padding: 16px; border-radius: 4px 8px 8px 4px; margin-bottom: 24px;">
                        <p style="margin: 0; color: #0F172A; font-weight: 700; font-size: 14.5px; line-height: 1.55;">
                            💡 {summary.get('one_liner', '')}
                        </p>
                    </div>

                    <!-- 키워드 영역 -->
                    <div style="margin-bottom: 26px;">
                        {keywords_html}
                    </div>

                    <hr style="border: 0; border-top: 1px solid #E5E7EB; margin-bottom: 24px;">

                    <!-- 주요 챕터 요약 -->
                    <div style="margin-bottom: 26px;">
                        <h3 style="margin: 0 0 16px 0; color: {badge_color}; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">
                            주요 핵심 내용
                        </h3>
                        {chapters_html}
                    </div>

                    <!-- 총평 및 인사이트 -->
                    <div style="background-color: #F9FAFB; border: 1px solid #F1F5F9; border-radius: 12px; padding: 18px;">
                        <h4 style="margin: 0 0 8px 0; color: #1E1B4B; font-size: 14px; font-weight: 800;">
                            📌 핵심 인사이트 & 시사점
                        </h4>
                        <p style="margin: 0; color: #4B5563; font-size: 13.5px; line-height: 1.6; white-space: pre-line;">
                            {summary.get('insights', '')}
                        </p>
                    </div>
                </td>
            </tr>
            <!-- 푸터 -->
            <tr>
                <td style="background-color: #F9FAFB; padding: 18px; text-align: center; border-top: 1px solid #E5E7EB;">
                    <p style="margin: 0; color: #9CA3AF; font-size: 12px;">본 메일은 [{channel_name}] 신규 영상을 AI가 요약하여 개별 발송하는 안내 메일입니다.</p>
                    <p style="margin: 4px 0 0 0; color: #9CA3AF; font-size: 11px;">&copy; {datetime.now().year} {channel_name} AI Summary Service. All rights reserved.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject_str, "utf-8")
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    server.send_message(msg)
    safe_print(f"[SUCCESS] Individual email sent to {receiver_email} for [{channel_name}]: {title}")

def send_summary_email(force=False):
    data_path = os.path.abspath(os.path.join("public", "data.json"))
    
    if not os.path.exists(data_path):
        safe_print("[ERROR] Database file public/data.json not found. Cannot send email.")
        return False
        
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        safe_print(f"[ERROR] Failed to read database file: {e}")
        return False
        
    if not data:
        safe_print("[INFO] Database is empty. No summary to email.")
        return False

    target_items = []

    if force:
        # force 옵션 시 미발송 항목 전체 또는 최신 3개 항목 개별 발송
        unsent = [item for item in data if not item.get("email_sent", False)]
        target_items = unsent if unsent else data[:3]
    else:
        # 미발송(email_sent != True) 상태인 모든 신규 요약 항목 수집
        for item in data:
            if not item.get("email_sent", False):
                target_items.append(item)

    if not target_items:
        safe_print("[INFO] All video summaries have already been emailed. No unsent items.")
        return True

    safe_print(f"[INFO] Found {len(target_items)} unsent video summary(ies). Sending individual emails...")

    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()
    receiver_email = os.getenv("RECEIVER_EMAIL", "").strip()
    
    sender_password = sender_password.replace(" ", "")
    
    if not sender_email or not sender_password or not receiver_email:
        safe_print("[ERROR] Email SMTP configuration missing in .env file.")
        return False

    if sender_email == "your_gmail_username@gmail.com":
        safe_print("[ERROR] Default placeholder values found in .env.")
        return False

    sent_count = 0
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)

        for item in target_items:
            try:
                send_individual_email(server, sender_email, receiver_email, item)
                item["email_sent"] = True
                sent_count += 1
            except Exception as e:
                safe_print(f"[ERROR] Failed to send email for video {item.get('id')}: {e}")

        server.quit()
    except Exception as e:
        safe_print(f"[ERROR] SMTP server connection error: {e}")
        return False

    # 발송 여부(email_sent=True) 상태를 public/data.json에 업데이트 저장
    if sent_count > 0:
        try:
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            safe_print(f"[SUCCESS] Updated public/data.json with email_sent=True for {sent_count} item(s).")
        except Exception as e:
            safe_print(f"[WARNING] Failed to update data.json after email send: {e}")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Individual YouTube Summary Emails")
    parser.add_argument("--force", action="store_true", help="Force send unsent or latest summary emails")
    args = parser.parse_args()
    
    success = send_summary_email(force=args.force)
    if not success:
        sys.exit(1)
