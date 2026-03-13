import httpx
from config import settings

_BASE = f"https://api.telegram.org/bot{settings.telegram_token}"


async def send_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )


async def send_inline_keyboard(
    chat_id: int, text: str, buttons: list[list[dict]]
) -> int:
    """Returns message_id of the sent message."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": buttons},
            },
            timeout=10.0,
        )
        data = resp.json()
        return data.get("result", {}).get("message_id", 0)


async def answer_callback_query(callback_query_id: str, text: str = "") -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{_BASE}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=10.0,
        )


async def remove_inline_keyboard(chat_id: int, message_id: int) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{_BASE}/editMessageReplyMarkup",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            },
            timeout=10.0,
        )
