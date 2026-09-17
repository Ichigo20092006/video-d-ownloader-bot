from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import uuid

app = FastAPI(title="Telegram-Bot Style Video Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def remove_file(path: str):
    """Удаляет файл с сервера после успешной отправки в Android"""
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error removing temporary file: {e}")

@app.get("/download")
def download_video(url: str, background_tasks: BackgroundTasks):
    if not url:
        raise HTTPException(status_code=400, detail="URL matches empty string")

    # Генерируем уникальное случайное имя файла на сервере
    unique_id = str(uuid.uuid4())[:8]
    output_template = f"/tmp/downloaded_video_{unique_id}.%(ext)s"

    ydl_opts = {
        # Скачиваем лучшее mp4 видео со звуком воедино
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Сервер сам скачивает видео к себе на диск (как Телеграм Бот)
            info = ydl.extract_info(url, download=True)
            
            # Получаем реальное название видео для отправки в Android
            video_title = info.get('title', f"video_{unique_id}")
            safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
            if not safe_title:
                safe_title = "downloaded_video"

            # Находим скачанный файл на диске сервера
            actual_filename = ydl.prepare_filename(info)
            
            # На бесплатных хостингах расширение может измениться, проверяем физический файл
            if not os.path.exists(actual_filename):
                # Если yt-dlp сохранил с другим расширением, ищем его в папке /tmp/
                base_path = f"/tmp/downloaded_video_{unique_id}"
                for f in os.listdir("/tmp"):
                    if f.startswith(f"downloaded_video_{unique_id}"):
                        actual_filename = os.path.join("/tmp", f)
                        break

            if not os.path.exists(actual_filename):
                raise HTTPException(status_code=404, detail="Файл не скачался на сервер")

            # 2. Добавляем фоновую задачу на удаление файла ПОСЛЕ того, как Android его скачает
            background_tasks.add_task(remove_file, actual_filename)

            # 3. Отправляем готовый чистый физический файл в Android-приложение!
            return FileResponse(
                path=actual_filename,
                media_type="video/mp4",
                filename=f"{safe_title}.mp4"
            )

    except Exception as e:
        # В случае ошибки очищаем диск
        base_path = f"/tmp/downloaded_video_{unique_id}"
        for ext in ['.mp4', '.mkv', '.webm', '.part']:
            if os.path.exists(base_path + ext):
                remove_file(base_path + ext)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"status": "Бот-сервер работает в режиме прямого скачивания файлов!"}
