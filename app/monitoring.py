from __future__ import annotations
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import asyncio

app = FastAPI(title="resume-bot-monitoring")

REQUESTS = Counter("resume_requests_total", "Все события", ["type"])  # score, full, cover
FAILURES = Counter("resume_failures_total", "Ошибки", ["stage"])  # parse, llm, other
LLM_LATENCY = Histogram("resume_llm_latency_seconds", "Время ответа LLM" )

@app.get("/healthz")
async def health() -> dict:
    return {"ok": True}

@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
