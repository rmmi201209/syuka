import os
import sys
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

# 업로드할 대상 파일 목록 (로컬 파일 경로 -> 깃허브 저장소 경로)
FILES_TO_UPLOAD = {
    "requirements.txt": "requirements.txt",
    ".gitignore": ".gitignore",
    os.path.join("public", "data.json"): "public/data.json",
    os.path.join("scripts", "check_and_summarize.py"): "scripts/check_and_summarize.py",
    os.path.join("scripts", "send_email.py"): "scripts/send_email.py",
    os.path.join(".github", "workflows", "scheduler.yml"): ".github/workflows/scheduler.yml"
}

def upload_file_to_github(token, owner, repo, local_path, github_path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{github_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    if not os.path.exists(local_path):
        print(f"[SKIP] Local file not found: {local_path}")
        return False

    with open(local_path, "rb") as f:
        content_bytes = f.read()

    base64_content = base64.b64encode(content_bytes).decode("utf-8")

    # 기존 파일 SHA 확인 (업데이트용)
    get_res = requests.get(url, headers=headers)
    sha = None
    if get_res.status_code == 200:
        sha = get_res.json().get("sha")

    payload = {
        "message": f"Upload {github_path} via auto script",
        "content": base64_content
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(url, headers=headers, json=payload)
    if put_res.status_code in [200, 201]:
        print(f"[SUCCESS] Uploaded to GitHub: {github_path}")
        return True
    else:
        print(f"[ERROR] Failed to upload {github_path}: {put_res.status_code} - {put_res.text}")
        return False

def main():
    token = os.getenv("GITHUB_TOKEN")
    username = os.getenv("GITHUB_USERNAME")
    repo = os.getenv("GITHUB_REPO", "syuka")

    if not token:
        token = input("GitHub Personal Access Token을 입력하세요: ").strip()
    if not username:
        username = input("GitHub 사용자 이름(Username)을 입력하세요: ").strip()

    print(f"\n[INFO] Starting auto upload to GitHub repository: {username}/{repo}...")

    success_count = 0
    for local_p, github_p in FILES_TO_UPLOAD.items():
        if upload_file_to_github(token, username, repo, local_p, github_p):
            success_count += 1

    print(f"\n[SUMMARY] Successfully uploaded {success_count}/{len(FILES_TO_UPLOAD)} files to GitHub!")

if __name__ == "__main__":
    main()
