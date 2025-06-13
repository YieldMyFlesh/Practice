from fastapi import FastAPI, Query, HTTPException
from yt_dlp import YoutubeDL

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "OK"}

app = FastAPI()

@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    ydl_opts = {'quiet': True, 'noplaylist': True, 'extract_flat': False}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch10:{q}", download=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка yt_dlp: {e}")

    if not search_result or "entries" not in search_result:
        return {"results": []}

    results = []
    for entry in search_result.get("entries", []):
        if entry is None:
            continue
        title = entry.get("title")
        video_id = entry.get("id")
        duration = entry.get("duration", 0)
        if title and video_id:
            results.append({
                "title": title,
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "duration": duration
            })

    return {"results": results}
