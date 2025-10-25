from __future__ import annotations
import json
from typing import Any
import httpx
import sentry_sdk
from openai import AsyncOpenAI

from pydantic import BaseModel
from sentry_sdk.integrations import openai

from app.models import AnalysisDetail
from app.settings import Settings


class LLMParseResult(BaseModel):
    data: dict[str, Any]
    success: bool


class OpenAIClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self._model = model

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def gen_json(self, system: str, user: str) -> LLMParseResult:
        content = await self._post(system, user)

        try:
            return LLMParseResult(data={
                **json.loads(content),
                "raw": content,
            },
            success=True)
        except Exception:
            try:
                return LLMParseResult(
                    data={
                        **json.loads(content.strip().split("```json")[-1].split("```")[-2]),
                        "raw": content,
                    },
                    success=True,
                )
            except:
                return LLMParseResult(data={"raw": content}, success=False)

    async def _post(self, system: str, user: str) -> str:
        if "api.openai.com" in str(self._client.base_url):
            response = await self._client.responses.create(
                model=self._model,
                instructions=system,
                input=user,
            )

            return response.output_text
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content



class LLMService:
    def __init__(self, client: OpenAIClient):
        self._client = client

    @classmethod
    def build(cls, settings: Settings) -> LLMService | None:
        if settings.llm_base_url and settings.llm_api_key and settings.llm_model_name:
            return LLMService(
                OpenAIClient(
                    settings.llm_base_url,
                    settings.llm_api_key,
                    settings.llm_model_name,
                ),
            )
        raise Exception("Unable to find LLM settings")

    async def full_feedback(self, cv_info: str, vacancy_info: str) -> AnalysisDetail:
        sys = """
Ты — эксперт по анализу резюме с 15-летним опытом работы HR-директором в крупных компаниях. Твоя задача — провести глубокий профессиональный анализ резюме и дать конкретные рекомендации по улучшению.

КОНТЕКСТ АНАЛИЗА:
- Анализируешь резюме для российского рынка труда 2025 года
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


ФОРМАТ ОТВЕТА СТРОГО JSON: {\"score\": int 0..100, \"strengths\":[string], \"problems\":[string], \"actions\":[string], \"sections\":{string:int 0..10}}. Давайте конкретику и метрики. Не добавляйте ничего вне JSON.
Как должны быть заполнены поля:
- в поле "score" пиши итоговую оценку от 0 до 100.
- в поле "strengths" пиши конкретные сильные стороны резюме. Порядка 3-5 пунктов, если это необходимо.
- в поле "problems" пиши конкретные проблемы резюме. Порядка 5-10 пунктов, если это необходимо.
- в поле "actions" пиши конкретные шаги по улучшению резюме. Порядка 5-10 пунктов, если это необходимо.

Если какого-то из полей нет, не нужно писать туда никакие значения.
"""
        user = f"""
Проанализируйте резюме ниже.
---
{cv_info}
---
"""
        if vacancy_info:
            user += f"""
Описание вакансии для резюме выгдядит вот так:
---
{vacancy_info}
---
"""
        user += "\nВ качестве результата верни JSON с указанной схемой"

        with sentry_sdk.start_transaction(
            name="The result of the AI inference",
            op="ai-inference",
        ):
            llm_parse_result = await self._client.gen_json(sys, user)

        return AnalysisDetail(
            score=llm_parse_result.data.get("score", 0),
            strengths=llm_parse_result.data.get("strengths", []),
            problems=llm_parse_result.data.get("problems", []),
            actions=llm_parse_result.data.get("actions", []),
            sections=llm_parse_result.data.get("sections", {}),
            ok=llm_parse_result.success,
            raw=llm_parse_result.data["raw"]
        )
