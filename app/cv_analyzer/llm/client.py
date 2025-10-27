import json
import logging
import re
from typing import Any

import json_repair
from openai import BaseModel, AsyncOpenAI

from app.settings import LLMSettings

logger = logging.getLogger(__name__)


def remove_control_characters_re(text):
    # Matches Unicode control characters in ranges U+0000-U+001F and U+007F-U+009F
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)


class LLMParseResult(BaseModel):
    data: dict[str, Any]
    raw: str
    success: bool


class OpenAIClient:
    def __init__(self, settings: LLMSettings):
        self._model = settings.general_model
        self._small_model = settings.small_model

        self._client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    async def gen_json(self, system: str, user: str, use_small_model: bool = False) -> LLMParseResult:
        content = await self._post(system, user, use_small_model=use_small_model)

        try:
            return LLMParseResult(
                data=json_repair.loads(remove_control_characters_re(content)),
                success=True,
                raw=content,
            )
        except Exception:
            try:
                logger.exception("Unable to parse LLM response as JSON")
                return LLMParseResult(
                    data=json.loads(content.strip().split("```json")[-1].split("```")[-2]),
                    success=True,
                    raw=content,
                )
            except:
                logger.exception("Unable to parse LLM response second time")
                return LLMParseResult(
                    data={},
                    success=False,
                    raw=content,
                )

    async def _post(self, system: str, user: str, use_small_model: bool) -> str:
        if "api.openai.com" in str(self._client.base_url):
            response = await self._client.responses.create(
                model=self._small_model if use_small_model else self._model,
                instructions=system,
                input=user,
            )

            return response.output_text
        else:
            response = await self._client.chat.completions.create(
                model=self._small_model if use_small_model else self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content
