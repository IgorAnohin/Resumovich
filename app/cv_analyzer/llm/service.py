import logging
import sentry_sdk

from app.cv_analyzer.llm.client import OpenAIClient
from app.models import AnalysisDetail, CheckFileResult
from app.settings import Settings, LLMSettings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, client: OpenAIClient):
        self._client = client

    @classmethod
    def build(cls, settings: LLMSettings) -> "LLMService":
        return LLMService(OpenAIClient(settings))

    async def check_resume_is_valid(self, cv_info: str) -> CheckFileResult:
        sys = """
Ты — фильтр входящих сообщений.  Твоя задача - определить, похоже ли сообщение пользователя на текст резюме.  

Резюме — это структурированный текст, содержащий хотя бы часть полей: 
«опыт работы», «образование», «навыки», «о себе», «контакты», «должность», «компания», «период работы», «сертификаты».  
Обычно текст описывает профессиональный опыт, образование и навыки, иногда пунктами.  

Если пользователь отправил изображение, ссылку, приветствие, случайный текст, мем, вопрос, жалобу, список покупок или что-то, не похожее на резюме — это НЕ резюме.

ФОРМАТ ОТВЕТА СТРОГО JSON: {\"is_valid\": bool, \"reason\": string}. Если текст похож на описание резюме, установи "is_valid" в true. Если нет - в false и укажи причину в "reason".
"""

        user = f"""
Проверь, является ли следующий текст резюме:
---
{cv_info}
---
"""
        result = await self._client.gen_json(sys, user, use_small_model=True)
        return CheckFileResult(
            is_valid=result.data.get("is_valid", True),
            reason=result.data.get("reason", ""),
        )

    async def check_vacancy_is_valid(self, vacancy_info: str) -> CheckFileResult:
        sys = """
    Ты — фильтр входящих сообщений. Твоя задача - определить, похоже ли сообщение пользователя на описание вакансии. Если нет - укажи почему.

    Описание вакансии — это текст, в котором говорится о требованиях, задачах, обязанностях или условиях работы.  
    Обычно там упоминаются слова вроде: «вакансия», «требования», «обязанности», «опыт», «компания», «гибрид», «офис», «стек», «мы ищем», «будет плюсом», «от кандидата требуется».  
    Текст может быть скопирован с сайта или написан своими словами, но должен явно относиться к профессиональной позиции или роли.  

    Если пользователь отправил случайный текст, приветствие, шутку, мем, ссылку, вопрос, песню, список покупок или сообщение, не связанное с вакансией — это не описание вакансии.

    ФОРМАТ ОТВЕТА СТРОГО JSON: {\"is_valid\": bool, \"reason\": string}. Если текст похож на описание вакансии, установи "is_valid" в true. Если нет - в false и укажи причину в "reason".
    """

        user = f"""
    Проверь, является ли следующий текст описанием вакансии:
    ---
    {vacancy_info}
    ---
    """
        result = await self._client.gen_json(sys, user, use_small_model=True)
        return CheckFileResult(
            is_valid=result.data.get("is_valid", True),
            reason=result.data.get("reason", ""),
        )

    async def full_feedback(self, cv_info: str, vacancy_info: str) -> AnalysisDetail:
        sys = """
Ты — эксперт по анализу резюме с 15-летним опытом работы HR-директором в крупных компаниях. Твоя задача — провести глубокий профессиональный анализ резюме и дать конкретные рекомендации по улучшению.

КОНТЕКСТ АНАЛИЗА:
- Анализируешь резюме для российского рынка труда 2025 года
- Учитываешь требования ATS-систем hh.ru, Работа.ру и корпоративных систем подбора
- Учитывай резюме с hh.ru, которые скорее всего будут иметь специальную шапку. В такие нельзя вставить summary или изменить структуру
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
        user += "\nВ качестве результата верни JSON С УКАЗАННОЙ СХЕМОЙ"

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
            raw=llm_parse_result.raw,
            prompt=sys + "\n" + user,
        )
