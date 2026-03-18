import hashlib
import json
import csv
import io
import random

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import (
    init_db,
    is_survey_active, set_survey_active,
    save_response, get_all_responses, get_response_count, clear_responses,
    get_all_expectations, get_all_responses_full,
    get_stats_batch
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TOPICS = [
    {"id": 1, "icon": "🧠", "title": "Основы работы нейросетей", "category": "Теория", "color": "#003082"},
    {"id": 2, "icon": "💼", "title": "Принципы внедрения ИИ в бизнес", "category": "Теория", "color": "#003082"},
    {"id": 3, "icon": "✍️", "title": "Основы промптинга", "category": "Практика", "color": "#0E7C47"},
    {"id": 4, "icon": "🔧", "title": "Создание агента в NoCode (n8n)", "category": "Практика", "color": "#0E7C47"},
    {"id": 5, "icon": "🏭", "title": "ДаВинчи и корп. системы", "category": "Демо", "color": "#E31E24"},
    {"id": 6, "icon": "🚀", "title": "Разработка ПО за 2 часа вместо 2 лет", "category": "Демо", "color": "#E31E24"},
    {"id": 7, "icon": "📊", "title": "Применение ИИ в вашей области", "category": "Кейс-стади", "color": "#7C3AED"},
]


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
@app.get("/qr", response_class=HTMLResponse)
def qr_page(request: Request):
    return templates.TemplateResponse("qr.html", {"request": request})


@app.get("/opros", response_class=HTMLResponse)
def opros_page(request: Request):
    if not is_survey_active():
        return templates.TemplateResponse("closed.html", {"request": request})
    items = TOPICS[:]
    random.shuffle(items)
    return templates.TemplateResponse("opros.html", {"request": request, "items": items})


@app.get("/results", response_class=HTMLResponse)
def results_page(request: Request):
    return templates.TemplateResponse("results.html", {"request": request})


@app.post("/api/submit")
def submit(data: dict, request: Request):
    if not is_survey_active():
        raise HTTPException(status_code=403, detail="Опрос остановлен")

    client_hash = hashlib.sha256(
        (request.headers.get("user-agent", "") + request.client.host).encode()
    ).hexdigest()
    expectations = (data.get("expectations") or "").strip() or None
    save_response(json.dumps(data["ranking"]), client_hash, expectations=expectations)
    return {"status": "ok", "total": get_response_count()}


@app.get("/api/stats")
def stats():
    # Single HTTP request to Turso for all data
    rankings, expectations_list, active = get_stats_batch()
    total = len(rankings)

    avg_ranks = {}
    if total > 0:
        sums = {}
        counts = {}
        for r in rankings:
            ranking = json.loads(r)
            for pos, topic_id in enumerate(ranking):
                sums[topic_id] = sums.get(topic_id, 0) + (pos + 1)
                counts[topic_id] = counts.get(topic_id, 0) + 1
        for tid in sums:
            avg_ranks[tid] = round(sums[tid] / counts[tid], 2)

    return {
        "total": total,
        "avg_ranks": avg_ranks,
        "is_active": active,
        "expectations": expectations_list
    }


@app.post("/api/activate")
def activate():
    count = clear_responses()
    set_survey_active(True)
    return {"status": "activated", "cleared": count}


@app.post("/api/deactivate")
def deactivate():
    set_survey_active(False)
    return {"status": "deactivated"}


@app.get("/api/export")
def export_csv():
    responses = get_all_responses_full()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "ranking", "expectations"])
    for i, row in enumerate(responses, 1):
        writer.writerow([i, row[0], row[1] or ""])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=responses.csv"}
    )
