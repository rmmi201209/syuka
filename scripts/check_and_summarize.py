import os
import sys
import json
import time
import tempfile
import argparse
from datetime import datetime, timezone, timedelta
import feedparser
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
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

DEFAULT_CHANNELS = [
    {
        "id": "UCsJ6RuBiTVWRX156FVbeaGg",
        "name": "슈카월드",
        "handle": "@syukaworld",
        "badge_color": "#4F46E5"
    },
    {
        "id": "UChlv4GSd7OQl3js-jkLOnFA",
        "name": "삼프로TV",
        "handle": "@3protv",
        "badge_color": "#2563EB"
    },
    {
        "id": "UCCxgS_J2m_ksXNjsRnHZ4Pg",
        "name": "박정호교수의 여의도맨션",
        "handle": "@yeouidomansion",
        "badge_color": "#059669"
    }
]

def load_channels():
    channels_path = os.path.abspath("channels.json")
    if os.path.exists(channels_path):
        try:
            with open(channels_path, "r", encoding="utf-8") as f:
                channels = json.load(f)
                if channels:
                    return channels
        except Exception as e:
            safe_print(f"[WARNING] Failed to load channels.json: {e}")
    return DEFAULT_CHANNELS

def load_existing_video_ids():
    data_file = os.path.abspath(os.path.join("public", "data.json"))
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data_list = json.load(f)
                return {item.get("id") for item in data_list if item.get("id")}
        except Exception as e:
            safe_print(f"[WARNING] Failed to load existing data.json: {e}")
    return set()

def check_new_videos_by_channel(force_video_id=None, check_hours=72, max_per_channel=2):
    channels = load_channels()
    existing_ids = load_existing_video_ids()

    if force_video_id:
        safe_print(f"[INFO] Forcing processing for Video ID: {force_video_id}")
        return [{
            "id": force_video_id,
            "title": f"Test Video ({force_video_id})",
            "channel_id": channels[0]["id"],
            "channel_name": channels[0]["name"],
            "badge_color": channels[0].get("badge_color", "#4F46E5"),
            "published": datetime.now(timezone.utc).isoformat()
        }]

    videos_by_channel = []
    now = datetime.now(timezone.utc)
    check_delta = timedelta(hours=check_hours)

    safe_print(f"[INFO] Monitoring {len(channels)} channel(s). Check window: {check_hours} hours...")

    from googleapiclient.discovery import build
    
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        safe_print("[ERROR] YOUTUBE_API_KEY is missing in .env file. Cannot fetch videos.")
        return []

    youtube = build("youtube", "v3", developerKey=youtube_api_key)
    
    for ch in channels:
        ch_id = ch["id"]
        ch_name = ch["name"]
        badge_color = ch.get("badge_color", "#4F46E5")

        safe_print(f"[INFO] Fetching videos via YouTube Data API for [{ch_name}]")
        try:
            uploads_playlist_id = "UU" + ch_id[2:]
            playlist_response = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=max_per_channel
            ).execute()
        except Exception as e:
            safe_print(f"[ERROR] Failed to fetch channel {ch_name} via API: {e}")
            continue

        if not playlist_response.get("items"):
            safe_print(f"[INFO] No video entries found for {ch_name}.")
            continue

        ch_count = 0
        for item in playlist_response["items"]:
            if ch_count >= max_per_channel:
                break

            video_id = item["snippet"]["resourceId"]["videoId"]
            if not video_id or video_id in existing_ids:
                continue

            title = item["snippet"]["title"]
            published_at = item["snippet"]["publishedAt"]
            published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))

            time_diff = now - published_dt

            if time_diff <= check_delta:
                safe_print(f"[NEW] Found recent video in [{ch_name}]: {title} ({video_id}) - Published {published_dt.isoformat()}")
                videos_by_channel.append({
                    "id": video_id,
                    "title": title,
                    "channel_id": ch_id,
                    "channel_name": ch_name,
                    "badge_color": badge_color,
                    "published": published_dt.isoformat()
                })
                ch_count += 1


    return videos_by_channel

def get_transcript(video_id):
    safe_print(f"[INFO] Trying YouTube Transcript API for Video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id, languages=["ko"])
        
        full_text = []
        for segment in transcript_list:
            text = segment.text.strip()
            start_sec = int(segment.start)
            minutes = start_sec // 60
            seconds = start_sec % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            full_text.append(f"{timestamp} {text}")

        safe_print(f"[SUCCESS] Successfully fetched transcript ({len(full_text)} segments).")
        return "\n".join(full_text)
    except Exception as e:
        safe_print(f"[WARNING] YouTube Transcript API failed for {video_id}: {e}")
        return None

def download_audio(video_id):
    safe_print(f"[INFO] Downloading audio via yt-dlp for Video ID: {video_id}...")
    temp_dir = tempfile.gettempdir()
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_dir, f'syuka_{video_id}.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
        for ext in ['mp3', 'm4a', 'webm', 'wav']:
            target_path = os.path.join(temp_dir, f'syuka_{video_id}.{ext}')
            if os.path.exists(target_path):
                safe_print(f"[SUCCESS] Audio downloaded to: {target_path}")
                return target_path

        return None
    except Exception as e:
        safe_print(f"[ERROR] Failed to download audio with yt-dlp: {e}")
        return None

def summarize_with_text_client(client, model_name, title, channel_name, transcript_text):
    from google.genai import types

    prompt = f"""
당신은 전문 유튜브 영상 요약 에디터이자 경제/시사 전문 뉴스레터 편집자입니다.
유튜브 채널 "{channel_name}"의 영상 제목 "{title}"에 대해 타임라인(자막)을 읽고, 독자들이 핵심을 빠르게 파악할 수 있도록 구조화된 한국어 요약문을 작성해주세요.

[자막]
{transcript_text}

[JSON 응답 구조]
{{
  "one_liner": "이 영상 전체 내용을 아우르는 핵심을 찌르는 강렬한 한 줄 요약",
  "keywords": ["주제키워드1", "주제키워드2", "주제키워드3"],
  "chapters": [
    {{
      "title": "첫 번째 핵심 주제",
      "timeline": "시작 타임라인 (예: 01:20)",
      "content": "상세 내용 요약 (수치, 내용, 배경 3~4줄)"
    }},
    {{
      "title": "두 번째 핵심 주제",
      "timeline": "시작 타임라인 (예: 08:45)",
      "content": "두 번째 주제 요약..."
    }}
  ],
  "insights": "이 영상이 주는 궁극적인 인사이트 및 시사점 정리 (3줄 내외)"
}}
"""
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                safe_print(f"[RETRY {attempt}/3] Gemini model {model_name} busy. Retrying in 3 seconds...")
                time.sleep(3)
            else:
                raise e
    return None

def summarize_with_audio_client(client, model_name, title, channel_name, audio_path):
    from google.genai import types

    safe_print(f"[INFO] Uploading audio file to Gemini API: {audio_path}")
    uploaded_file = client.files.upload(file=audio_path)
    safe_print(f"[SUCCESS] Audio uploaded to Gemini: {uploaded_file.name}")

    prompt = f"""
당신은 전문 유튜브 영상 요약 에디터이자 경제/시사 전문 뉴스레터 편집자입니다.
유튜브 채널 "{channel_name}"의 영상 제목 "{title}"의 오디오를 듣고 구조화된 한국어 요약문을 작성해주세요.

[JSON 응답 구조]
{{
  "one_liner": "이 영상 전체 내용을 아우르는 핵심을 찌르는 강렬한 한 줄 요약",
  "keywords": ["주제키워드1", "주제키워드2", "주제키워드3"],
  "chapters": [
    {{
      "title": "첫 번째 핵심 주제",
      "timeline": "시작 타임라인 (예: 01:20)",
      "content": "상세 내용 요약 (3~4줄)"
    }}
  ],
  "insights": "이 영상이 주는 궁극적인 인사이트 및 시사점 정리 (3줄 내외)"
}}
"""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        summary_text = response.text
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
            safe_print(f"[INFO] Deleted temporary Gemini file: {uploaded_file.name}")
        except Exception as e:
            safe_print(f"[WARNING] Failed to delete Gemini file: {e}")

    return summary_text

def summarize_transcript(video_id, title, channel_name, transcript_text):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        safe_print("[ERROR] GEMINI_API_KEY is not configured in .env file.")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        
        candidate_models = ["gemini-3.6-flash", "gemini-3.1-pro-preview", "gemini-2.0-flash", "gemini-1.5-flash"]
        
        if transcript_text:
            for model_name in candidate_models:
                safe_print(f"[INFO] Trying text summarization with Gemini model: {model_name}")
                try:
                    summary = summarize_with_text_client(client, model_name, title, channel_name, transcript_text)
                    if summary:
                        return summary
                except Exception as e:
                    safe_print(f"[WARNING] Text summarization with {model_name} failed: {e}")

        safe_print(f"[INFO] Text transcript unavailable/failed. Attempting audio fallback for Video ID: {video_id}...")
        audio_path = download_audio(video_id)
        if audio_path:
            for model_name in candidate_models:
                try:
                    summary = summarize_with_audio_client(client, model_name, title, channel_name, audio_path)
                    if summary:
                        return summary
                except Exception as e:
                    safe_print(f"[ERROR] Audio summarization with {model_name} failed: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
                safe_print(f"[INFO] Removed local audio temp file: {audio_path}")
                        
    except Exception as e:
        safe_print(f"[ERROR] Gemini SDK initialization failed: {e}")

    return None

def save_to_database(video_id, title, channel_id, channel_name, badge_color, published, summary_str):
    data_dir = os.path.abspath("public")
    data_file = os.path.join(data_dir, "data.json")
    os.makedirs(data_dir, exist_ok=True)

    data_list = []
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data_list = json.load(f)
        except Exception as e:
            safe_print(f"[WARNING] Failed to load existing data.json: {e}")
            data_list = []

    if any(item.get("id") == video_id for item in data_list):
        safe_print(f"[INFO] Video ID {video_id} already exists in database. Skipping.")
        return False, None

    try:
        clean_str = summary_str.strip()
        if clean_str.startswith("```json"):
            clean_str = clean_str[7:]
        if clean_str.startswith("```"):
            clean_str = clean_str[3:]
        if clean_str.endswith("```"):
            clean_str = clean_str[:-3]
        
        summary_data = json.loads(clean_str.strip())
    except Exception as e:
        safe_print(f"[ERROR] Failed to parse summary JSON: {e}")
        return False, None

    new_entry = {
        "id": video_id,
        "title": title,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "badge_color": badge_color,
        "published": published,
        "summary": summary_data,
        "email_sent": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    data_list.insert(0, new_entry)

    try:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        safe_print(f"[SUCCESS] Saved summary for [{channel_name}] {video_id} to public/data.json")
        return True, new_entry
    except Exception as e:
        safe_print(f"[ERROR] Failed to write data.json: {e}")
        return False, None

def main():
    parser = argparse.ArgumentParser(description="Multi-Channel YouTube Summarizer")
    parser.add_argument("--force", type=str, help="Process a specific video ID instead of monitoring feed")
    parser.add_argument("--hours", type=int, default=72, help="Monitoring check window in hours (default: 72)")
    parser.add_argument("--max", type=int, default=2, help="Max number of new videos to process PER CHANNEL (default: 2)")
    args = parser.parse_args()

    videos_to_process = check_new_videos_by_channel(force_video_id=args.force, check_hours=args.hours, max_per_channel=args.max)

    if not videos_to_process:
        safe_print("[INFO] No new videos found across monitored channels.")
        sys.exit(0)

    safe_print(f"[INFO] Processing {len(videos_to_process)} new video(s) across channels...")
    
    processed_count = 0
    saved_entries = []

    for video in videos_to_process:
        video_id = video["id"]
        title = video["title"]
        channel_name = video["channel_name"]
        channel_id = video["channel_id"]
        badge_color = video["badge_color"]
        published = video["published"]

        safe_print(f"\n--- [Processing: [{channel_name}] {title} ({video_id})] ---")

        transcript = get_transcript(video_id)
        summary_json = summarize_transcript(video_id, title, channel_name, transcript)
        
        if not summary_json:
            safe_print(f"[SKIP] Summary generation failed for: {video_id}")
            continue

        success, entry = save_to_database(video_id, title, channel_id, channel_name, badge_color, published, summary_json)
        if success:
            processed_count += 1
            saved_entries.append(entry)

    safe_print(f"\n[INFO] Multi-channel batch processing finished. {processed_count} new summaries created.")
    
    if saved_entries:
        safe_print(f"[METADATA] NEW_SUMMARIES_COUNT={len(saved_entries)}")

if __name__ == "__main__":
    main()
