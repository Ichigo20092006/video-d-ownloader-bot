from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Video Downloader API")

# Включаем CORS, чтобы к API можно было обращаться отовсюду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/parse")
def parse_video(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL matches empty string")
        
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Ищем mp4
        'quiet': True,
        'no_warnings': True,
        # Важные заголовки, чтобы соцсети не выдавали ошибку 403 / 429
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Если это плейлист или несколько видео, берем первое
            if 'entries' in info:
                video_data = info['entries'][0]
            else:
                video_data = info
                
            # Извлекаем прямой URL на видеофайл
            direct_url = video_data.get('url')
            title = video_data.get('title', 'video')
            
            if not direct_url:
                raise HTTPException(status_code=404, detail="Direct stream URL not found")
                
            return {
                "success": True,
                "title": title,
                "url": direct_url
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"status": "Server is running perfectly"}