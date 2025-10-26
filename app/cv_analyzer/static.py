from __future__ import annotations
import re
from typing import Dict, Any, List

from app.models import AnalysisDetail

SECTION_PATTERNS = [
    r"\bопыт работы\b", r"\bопыт\b", r"\bexperience\b",
    r"\bобразование\b", r"\beducation\b",
    r"\bнавыки\b", r"\bskills\b",
    r"\bпроекты\b", r"\bprojects?\b",
    r"\bсертификаты\b", r"\bcertifications?\b",
]

def analyze_resume_text(text: str) -> AnalysisDetail:
    clean = re.sub(r"[\u200b\ufeff\xa0]", " ", text, flags=re.I)
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9\-\+%$€₽]+", clean)
    word_count = len(words)

    sections_found: Dict[str, bool] = {}
    for pat in SECTION_PATTERNS:
        sections_found[pat] = bool(re.search(pat, clean, flags=re.I))

    numbers = re.findall(r"(\b\d{4}\b|\b\d+%\b|\b\d+[\.,]\d+\b|\b\d+\b)", clean)
    metrics_density = len(numbers) / max(1, word_count)

    bullets = len(re.findall(r"^[\s\-•·•*]+", clean, flags=re.M))
    contacts = re.search(r"@|\+\d|https?://|linkedin\.com|github\.com|portfolio", clean, flags=re.I) is not None

    score = 50
    key_sections = ["опыт", "образование", "навыки"]
    score += 10 * sum(int(any(re.search(k, kpat, flags=re.I) for k in key_sections) and v) for kpat, v in sections_found.items())
    score += min(20, int(metrics_density * 200))
    score += min(10, bullets // 5 * 2)
    score += 5 if contacts else -10
    score = max(0, min(100, score))

    suggestions: List[str] = []

    if word_count < 200:
        suggestions.append("Резюме слишком короткое. Добавьте 3–5 bullets на каждую роль с метриками.")
    if word_count > 1400:
        suggestions.append("Слишком объёмно. Сожмите до 1–2 страниц, уберите неактуальные роли.")
    if metrics_density < 0.01:
        suggestions.append("Добавьте количественные метрики: рост %, выручка, экономия времени/денег.")
    if bullets < 8:
        suggestions.append("Используйте маркированные пункты вместо сплошных абзацев.")
    if not contacts:
        suggestions.append("Добавьте контакты и ссылки: email, LinkedIn, GitHub/портфолио.")
    if not re.search(r"(?i)python|sql|java|js|golang|kotlin|swift|c\+\+|c#", clean):
        suggestions.append("Техстек не виден. Вынесите ключевые технологии в раздел 'Навыки'.")
    if not re.search(r"(?i)lead|руковод|менедж|team", clean):
        suggestions.append("Почти нет сигналов влияния/лидерства. Добавьте проекты, где вы вели людей/инициативы.")
    if not re.search(r"\b\d{4}\b", clean):
        suggestions.append("Не хватает дат по ролям. Укажите период и результаты." )

    findings: List[str] = []
    findings.append(f"Слов: {word_count}")
    findings.append(f"Плотность метрик: {metrics_density:.3f}")
    findings.append(f"Буллетов: {bullets}")
    findings.append("Контакты найдены" if contacts else "Контактов не найдено")

    return AnalysisDetail(
        score=score,
        strengths=[],
        problems=findings,
        actions=suggestions,
        sections=sections_found,
        ok=True,
        raw=text,
        prompt="static analize"
    )
