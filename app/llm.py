from __future__ import annotations
import json
from typing import Any, Dict
import httpx
import asyncio
import os

class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()

    async def gen_json(self, system: str, user: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        data = await self._post("/v1/chat/completions", payload)
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except Exception:
            # если провайдер не поддержал json_object, попытаемся вручную
            return json.loads(content.strip().split("```json")[-1].split("```")[-2])

async def score_resume(client: LLMClient, text: str) -> Dict[str, Any]:
    sys = "Вы оцениваете резюме. Верните только JSON со структурой: {\"score\": int 0..100, \"rationale\": string}. Будьте строги, но объективны."
    user = f"Резюме ниже между тремя чертами.\n---\n{text}\n---\nВерните JSON."
    return await client.gen_json(sys, user)

async def full_feedback(client: LLMClient, text: str) -> Dict[str, Any]:
    sys = "Вы делаете полный экспертный анализ резюме для IT в РФ, 2025. Формат ответа строго JSON: {\"score\": int 0..100, \"strengths\":[string], \"problems\":[string], \"actions\":[string], \"sections\":{string:int 0..10}}. Давайте конкретику и метрики. Не добавляйте ничего вне JSON."
    user = f"Проанализируйте резюме ниже и верните JSON с указанной схемой.\n---\n{text}\n---"
    return await client.gen_json(sys, user)

def build_client_from_env() -> LLMClient | None:
    base = os.environ.get("LLM_BASE_URL")
    key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL_NAME")
    if base and key and model:
        return LLMClient(base, key, model)
    return None
