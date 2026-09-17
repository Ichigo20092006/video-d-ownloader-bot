from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid
import requests  # Импортируем на самом верху, теперь библиотека точно будет найдена!

app = FastAPI(title="Telegram-Bot Style Video Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def remove_file(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

@app.get("/download")
def download_video(url: str, background_tasks: BackgroundTasks):
    if not url:
        raise HTTPException(status_code=400, detail="URL matches empty string")

    unique_id = str(uuid.uuid4())[:8]
    output_template = f"/tmp/video_{unique_id}.%(ext)s"
    safe_title = f"video_{unique_id}"

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios'], 'skip': ['webpage']},
            'instagram': {'apps': ['android']}
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', f"video_{unique_id}")
            safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
            if not safe_title:
                safe_title = "downloaded_video"

            actual_filename = ydl.prepare_filename(info)
            
            if not os.path.exists(actual_filename):
                for f in os.listdir("/tmp"):
                    if f.startswith(f"video_{unique_id}"):
                        actual_filename = os.path.join("/tmp", f)
                        break

            if not os.path.exists(actual_filename):
                raise HTTPException(status_code=404, detail="Файл не найден")

            background_tasks.add_task(remove_file, actual_filename)

            return FileResponse(
                path=actual_filename,
                media_type="video/mp4",
                filename=f"{safe_title}.mp4"
            )

    except Exception as e:
        # Если yt-dlp выдал ошибку rate-limit для Instagram, 
        # этот блок ТЕПЕРЬ ИДЕАЛЬНО подхватит загрузку через прокси-клиент Cobalt API!
        return download_via_server_fallback(url, safe_title=safe_title, background_tasks=background_tasks)

def download_via_server_fallback(url: str, safe_title: str, background_tasks: BackgroundTasks):
    try:
        payload = {"url": url, "vQuality": "720", "isAudioOnly": False}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        res = requests.post("https://api.cobalt.tools/api/json", json=payload, headers=headers, timeout=20)
        if res.status_code == 200:
            direct_url = res.json().get("url")
            if direct_url:
                tmp_path = f"/tmp/{safe_title}.mp4"
                
                # Скачиваем файл на сервер Render по байтам
                video_res = requests.get(direct_url, stream=True, timeout=40)
                with open(tmp_path, 'wb') as f:
                    for chunk in video_res.iter_content(chunk_size=512*1024):
                        if chunk:
                            f.write(chunk)
                            
                background_tasks.add_task(remove_file, tmp_path)
                return FileResponse(path=tmp_path, media_type="video/mp4", filename=f"{safe_title}.mp4")
                
        raise Exception("Резервные API шлюзы также перегружены")
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания: {str(err)}")

@app.get("/")
def root():
    return {"status": "Анти-бан сервер работает стабильно!"}
