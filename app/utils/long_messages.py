from aiogram.types import Message

TELEGRAM_LIMIT = 4096  # hard limit per message

def _split_text(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf:
            parts.append(buf)
            buf = ""

    # Try to split by double newlines, then by single newlines, then hard cut
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        candidate = (buf + ("\n\n" if buf else "") + paragraph)
        if len(candidate) <= limit:
            buf = candidate
            continue

        # flush current and split paragraph further by lines
        flush()
        line_buf = ""
        for line in paragraph.split("\n"):
            line = line.rstrip()
            cand_line = (line_buf + ("\n" if line_buf else "") + line)
            if len(cand_line) <= limit:
                line_buf = cand_line
                continue

            if line_buf:
                parts.append(line_buf)
                line_buf = ""

            # Hard cut very long single lines
            start = 0
            while start < len(line):
                end = min(start + limit, len(line))
                parts.append(line[start:end])
                start = end

        if line_buf:
            parts.append(line_buf)

    flush()
    return parts


async def send_long_message(message: Message, text: str, parse_mode: str = "HTML") -> None:
    for chunk in _split_text(text, 4000):
        await message.answer(chunk, parse_mode=parse_mode)
