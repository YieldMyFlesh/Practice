from fastapi import FastAPI, Query
from yt_dlp import YoutubeDL

app = FastAPI()

@app.get("/search")
def search_music(q: str = Query(..., description="Назва або посилання на пісню")):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            if q.startswith("http"):
                info = ydl.extract_info(q, download=False)
                results = [{
                    "title": info.get("title"),
                    "link": info.get("webpage_url"),
                    "duration": info.get("duration", 0)
                }]
            else:
                search_url = f"ytsearch5:{q}"
                info = ydl.extract_info(search_url, download=False)
                entries = info.get('entries', [])
                results = []
                for entry in entries:
                    results.append({
                        "title": entry.get("title"),
                        "link": f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "duration": entry.get("duration", 0)
                    })
            return {"query": q, "results": results}
        except Exception as e:
            return {"error": str(e)}
