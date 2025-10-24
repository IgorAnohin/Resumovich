from __future__ import annotations
import json
from typing import Any, Dict
import httpx
import asyncio
import os

from app.models import AnalysisDetail
from app.settings import Settings


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

    async def gen_json(self, system: str, user: str) -> tuple[Dict[str, Any], bool]:
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
            return json.loads(content), True
        except Exception:
            # если провайдер не поддержал json_object, попытаемся вручную
            try:
                return json.loads(content.strip().split("```json")[-1].split("```")[-2]), True
            except:
                return content, False


class LLMService:
    def __init__(self, client: LLMClient):
        self._client = client

    @classmethod
    def build(cls, settings: Settings) -> LLMService | None:
        if settings.llm_base_url and settings.llm_api_key and settings.llm_model_name:
            return LLMService(LLMClient(
                settings.llm_base_url,
                settings.llm_api_key,
                settings.llm_model_name,
            ))
        return None

    async def score_resume(self, text: str) -> Dict[str, Any]:
        sys = "Вы оцениваете резюме. Верните только JSON со структурой: {\"score\": int 0..100, \"rationale\": string}. Будьте строги, но объективны."
        user = f"Резюме ниже между тремя чертами.\n---\n{text}\n---\nВерните JSON."
        return await self._client.gen_json(sys, user)

    async def full_feedback(self, text: str) -> AnalysisDetail:
        sys = """
Ты — эксперт по анализу резюме с 15-летним опытом работы HR-директором в крупных IT-компаниях (Яндекс, Сбер, VK). Твоя задача — провести глубокий профессиональный анализ резюме и дать конкретные рекомендации по улучшению.

КОНТЕКСТ АНАЛИЗА:
- Анализируешь резюме для российского рынка труда 2025 года
- Фокус на IT и около-IT специальностях
- Учитываешь требования ATS-систем hh.ru, Работа.ру и корпоративных систем подбора
- Оцениваешь резюме так, как его увидит HR-менеджер за первые 30 секунд просмотра

СТРУКТУРА АНАЛИЗА:

1. ОБЩАЯ ОЦЕНКА (0-100 баллов)
Дай итоговую оценку резюме и объясни её в 2-3 предложениях.

ВАЖНЫЕ ПРАВИЛА:
- Будь конкретным: вместо "улучшите описание опыта" напиши что-то вроде "замените фразу «X» на «Y»"
- Цитируй проблемные места из резюме в кавычках «»
- Давай примеры улучшенных формулировок
- Указывай метрики и цифры, которых не хватает
- Игнорируй служебную информацию с job-сайтов
- Фокусируйся на проблемах, которые реально влияют на отклики


Формат ответа строго JSON: {\"score\": int 0..100, \"strengths\":[string], \"problems\":[string], \"actions\":[string], \"sections\":{string:int 0..10}}. Давайте конкретику и метрики. Не добавляйте ничего вне JSON.
Как должны быть заполнены поля:
- в поле "score" пиши итоговую оценку от 0 до 100.
- в поле "strengths" пиши конкретные сильные стороны резюме. Порядка 3-5 пунктов, если это необходимо.
- в поле "problems" пиши конкретные проблемы резюме. Порядка 5-10 пунктов, если это необходимо.
- в поле "actions" пиши конкретные шаги по улучшению резюме. Порядка 5-10 пунктов, если это необходимо.
"""
        user = f"Проанализируйте резюме ниже и верните JSON с указанной схемой.\n---\n{text}\n---"
        llm_result, ok = await self._client.gen_json(sys, user)
        return AnalysisDetail(
            score=llm_result.get("score", 0),
            strengths=llm_result.get("strengths", []),
            problems=llm_result.get("problems", []),
            actions=llm_result.get("actions", []),
            sections=llm_result.get("sections", {}),
            ok=ok,
            raw=json.dumps(llm_result, ensure_ascii=False)
        )
