import os
import sys
import json
import tempfile
import argparse
from datetime import datetime, timezone, timedelta
import feedparser
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 슈카월드 유튜브 채널 ID 및 RSS Feed
SYUKA_CHANNEL_ID = "UCsJ6RuBiTVWRX156FVbeaGg"
RSS_FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={SYUKA_CHANNEL_ID}"

def check_new_videos(force_video_id=None, check_hours=24):
    """
    YouTube RSS Feed를 통해 슈카월드 채널의 최근 동영상을 탐색합니다.
    RSS Feed는 봇 차단 없이 100% 안정적으로 동작합니다.
    """
    if force_video_id:
        print(f"[INFO] Forcing processing for Video ID: {force_video_id}")
        return [{
            "id": force_video_id,
            "title": f"Test Video ({force_video_id})",
            "published": datetime.now(timezone.utc).isoformat()
        }]

    print(f"[INFO] Fetching latest videos from RSS feed: {RSS_FEED_URL}")
    feed = feedparser.parse(RSS_FEED_URL)

    if feed.bozo:
        print(f"[WARNING] RSS feed parsing caution: {feed.bozo_exception}")

    if not feed.entries:
        print("[ERROR] No video entries found in RSS feed.")
        return []

    new_videos = []
    now = datetime.now(timezone.utc)
    check_delta = timedelta(hours=check_hours)

    print(f"[INFO] Found {len(feed.entries)} total entries in RSS feed. Checking window: {check_hours} hours...")

    for entry in feed.entries:
        video_id = entry.get("yt_videoid")
        if not video_id and "link" in entry:
            if "v=" in entry.link:
                video_id = entry.link.split("v=")[1].split("&")[0]

        title = entry.get("title", "Untitled Video")
        published_parsed = entry.get("published_parsed")

        if published_parsed:
            published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
        else:
            published_dt = now

        time_diff = now - published_dt

        if time_diff <= check_delta:
            print(f"[NEW] Found recent video: {title} ({video_id}) - Published {published_dt.isoformat()}")
            new_videos.append({
                "id": video_id,
                "title": title,
                "published": published_dt.isoformat()
            })

    return new_videos

def get_transcript(video_id):
    """
    1차: youtube-transcript-api를 사용하여 한국어 자막 대본을 가져옵니다.
    """
    print(f"[INFO] Trying to fetch transcript via YouTube Transcript API for Video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id, languages=['ko'])
        
        full_text = []
        for segment in transcript_list:
            text = segment.text.strip()
            start_sec = int(segment.start)
            minutes = start_sec // 60
            seconds = start_sec % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            full_text.append(f"{timestamp} {text}")

        print(f"[SUCCESS] Successfully fetched transcript ({len(full_text)} segments).")
        return "\n".join(full_text)
    except Exception as e:
        print(f"[WARNING] YouTube Transcript API failed for {video_id}: {e}")
        return None

def download_audio(video_id):
    """
    2차 Fallback: 자막을 가져오지 못했을 때, yt-dlp로 오디오 파일만 다운로드합니다.
    ffmpeg 없이 원본 오디오 스트림(m4a / webm) 그대로 빠르게 다운로드합니다.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[INFO] Fallback: Downloading audio for Video ID: {video_id} using yt-dlp...")
    
    temp_dir = tempfile.gettempdir()
    output_template = os.path.join(temp_dir, f"syuka_{video_id}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        for ext in ['m4a', 'webm', 'mp3', 'mp4', 'opus']:
            target_path = os.path.join(temp_dir, f"syuka_{video_id}.{ext}")
            if os.path.exists(target_path):
                print(f"[SUCCESS] Audio downloaded to: {target_path}")
                return target_path

        print(f"[ERROR] Audio file not found after download.")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to download audio with yt-dlp: {e}")
        return None

def summarize_with_text_client(client, model_name, title, transcript_text):
    """
    google-genai 최신 SDK를 사용한 텍스트 대본 요약
    """
    from google.genai import types

    prompt = f"""
너는 아주 유능한 유튜브 영상 요약 에디터이자 경제/시사 전문 뉴스레터 필진이야.
유튜브 영상 제목인 "{title}"과 아래 제공되는 영상의 타임라인별 대본(자막)을 읽고, 독자들이 대본을 직접 읽지 않고도 핵심을 아주 정확하고 깊이 있게 파악할 수 있도록 구조화된 한국어 요약문을 작성해줘.

대본 속의 타임라인 정보(예: [01:23])를 적극 참고하여, 주요 주제가 바뀌는 시점의 정확한 타임라인 정보와 핵심 요약을 짝지어 매칭해줘.
응답은 반드시 정해진 JSON 형식으로만 작성해야 하며, 어떠한 마크다운 백틱(```json)이나 부가 설명 없이 오직 유효한 JSON 문자열로만 응답해야 해.

[대본]
{transcript_text}

[JSON 응답 구조]
{{
  "one_liner": "이 영상 전체 내용을 아우르는 핵심을 찌르는 강렬한 한 줄 요약",
  "keywords": ["주제키워드1", "주제키워드2", "주제키워드3"],
  "chapters": [
    {{
      "title": "첫 번째 세부 주제 (예: 엔비디아 실적 발표와 주가 전망)",
      "timeline": "해당 단락의 대략적인 시작 타임라인 (분:초 형식, 예: 02:15)",
      "content": "이 주제에 대한 상세 내용 요약. 구체적인 수치(퍼센트, 달러, 개수 등), 인용 주장, 배경 상황 및 시사점을 풍부하게 담아서 3~4줄로 명확하게 요약해줘."
    }},
    {{
      "title": "두 번째 세부 주제",
      "timeline": "시작 타임라인 (예: 11:40)",
      "content": "두 번째 주제의 요약..."
    }}
  ],
  "insights": "이 영상이 주는 궁극적인 시사점 및 트렌드 전망에 대한 정리 (3줄 내외)"
}}
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return response.text

def summarize_with_audio_client(client, model_name, title, audio_path):
    """
    google-genai 최신 SDK를 사용한 오디오 음성 멀티모달 요약
    """
    from google.genai import types

    print(f"[INFO] Uploading audio file to Gemini File API: {audio_path}...")
    uploaded_file = client.files.upload(file=audio_path)
    print(f"[SUCCESS] Audio file uploaded successfully: {uploaded_file.name}")

    prompt = f"""
너는 아주 유능한 유튜브 영상 요약 에디터이자 경제/시사 전문 뉴스레터 필진이야.
제공된 오디오 파일은 유튜브 영상 "{title}"의 전체 음성 파일이야.
이 음성을 처음부터 끝까지 정밀하게 듣고 분석해서 독자들이 영상을 직접 보지 않고도 핵심을 완벽하게 파악할 수 있도록 구조화된 한국어 요약문을 작성해줘.

주요 주제가 전환되는 타임라인(분:초 형식)을 정확히 포착해서 세부 주제별로 챕터를 나눠줘.
응답은 반드시 정해진 JSON 형식으로만 작성해야 하며, 어떠한 마크다운 백틱이나 부가 설명 없이 오직 유효한 JSON 문자열로만 응답해줘.

[JSON 응답 구조]
{{
  "one_liner": "이 영상 전체 내용을 아우르는 핵심을 찌르는 강렬한 한 줄 요약",
  "keywords": ["주제키워드1", "주제키워드2", "주제키워드3"],
  "chapters": [
    {{
      "title": "첫 번째 세부 주제",
      "timeline": "시작 타임라인 (분:초 형식, 예: 01:20)",
      "content": "상세 내용 요약 (수치, 인용, 배경, 시사점 포함 3~4줄)"
    }},
    {{
      "title": "두 번째 세부 주제",
      "timeline": "시작 타임라인 (예: 08:45)",
      "content": "두 번째 주제 요약..."
    }}
  ],
  "insights": "이 영상이 주는 궁극적인 시사점 및 트렌드 전망 정리 (3줄 내외)"
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
            print(f"[INFO] Deleted temporary Gemini file: {uploaded_file.name}")
        except Exception as e:
            print(f"[WARNING] Failed to delete Gemini file: {e}")

    return summary_text

def summarize_transcript(video_id, title, transcript_text):
    """
    Gemini API를 사용하여 요약 수행
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("[ERROR] GEMINI_API_KEY is not configured or uses placeholder in .env file.")
        return None

    # google-genai 최신 SDK 우선 사용
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        
        # 사용 가능한 모델 동적 탐색 (gemini-3.6-flash 최우선)
        candidate_models = ["gemini-3.6-flash"]
        try:
            available = list(client.models.list())
            for m in available:
                m_id = m.name.replace("models/", "") if hasattr(m, "name") else ""
                if "gemini" in m_id and m_id not in candidate_models:
                    candidate_models.append(m_id)
            print(f"[INFO] Discovered Gemini models: {candidate_models[:5]}")
        except Exception as e:
            print(f"[WARNING] Could not list models: {e}")

        if not candidate_models:
            candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        
        for model_name in candidate_models:
            print(f"[INFO] Trying Gemini model: {model_name}")
            
            # 1. 대본 텍스트 요약
            if transcript_text:
                try:
                    summary = summarize_with_text_client(client, model_name, title, transcript_text)
                    if summary:
                        return summary
                except Exception as e:
                    print(f"[WARNING] Text summarization with {model_name} failed: {e}")

            # 2. 오디오 분석 Fallback
            audio_path = download_audio(video_id)
            if audio_path:
                try:
                    summary = summarize_with_audio_client(client, model_name, title, audio_path)
                    if summary:
                        return summary
                except Exception as e:
                    print(f"[ERROR] Audio summarization with {model_name} failed: {e}")
                finally:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                        print(f"[INFO] Removed local audio temp file: {audio_path}")
                        
    except Exception as e:
        print(f"[ERROR] Gemini SDK initialization failed: {e}")

    return None

def save_to_database(video_id, title, published, summary_str):
    """
    요약본 데이터를 public/data.json에 누적하여 저장합니다.
    """
    data_dir = os.path.abspath("public")
    data_file = os.path.join(data_dir, "data.json")

    os.makedirs(data_dir, exist_ok=True)

    data_list = []
    if os.path.exists(data_file):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data_list = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load existing data.json, starting fresh: {e}")
            data_list = []

    if any(item.get("id") == video_id for item in data_list):
        print(f"[INFO] Video ID {video_id} already exists in database. Skipping saving.")
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
        print(f"[ERROR] Failed to parse summary string as JSON: {e}")
        print(f"[DEBUG] Raw summary: {summary_str}")
        return False, None

    new_entry = {
        "id": video_id,
        "title": title,
        "published": published,
        "summary": summary_data,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    data_list.insert(0, new_entry)

    try:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] Saved summary for {video_id} to public/data.json")
        return True, new_entry
    except Exception as e:
        print(f"[ERROR] Failed to write data.json: {e}")
        return False, None

def main():
    parser = argparse.ArgumentParser(description="Syuka World YouTube Summarizer")
    parser.add_argument("--force", type=str, help="Process a specific video ID instead of monitoring feed")
    parser.add_argument("--hours", type=int, default=48, help="Monitoring check window in hours (default: 48)")
    parser.add_argument("--max", type=int, default=1, help="Max number of new videos to process per run (default: 1)")
    args = parser.parse_args()

    # 1. RSS 피드 기반 신규 영상 체크
    new_videos = check_new_videos(force_video_id=args.force, check_hours=args.hours)

    if not new_videos:
        print("[INFO] No new videos found.")
        sys.exit(0)

    videos_to_process = new_videos[:args.max]
    print(f"[INFO] Processing {len(videos_to_process)} video(s) (out of {len(new_videos)} found)...")
    
    processed_count = 0
    saved_entries = []

    for video in videos_to_process:
        video_id = video["id"]
        title = video["title"]
        published = video["published"]

        print(f"\n--- [Processing: {title} ({video_id})] ---")

        # 2. 자막 추출 시도
        transcript = get_transcript(video_id)

        # 3. Gemini 요약 수행
        summary_json = summarize_transcript(video_id, title, transcript)
        if not summary_json:
            print(f"[SKIP] Summary generation failed for video: {title} ({video_id})")
            continue

        # 4. JSON 저장
        success, entry = save_to_database(video_id, title, published, summary_json)
        if success:
            processed_count += 1
            saved_entries.append(entry)

    print(f"\n[INFO] Batch processing finished. {processed_count} new summaries created.")
    
    if saved_entries:
        print(f"[METADATA] NEW_SUMMARIES_COUNT={len(saved_entries)}")

if __name__ == "__main__":
    main()
