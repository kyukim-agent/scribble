from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks

from cache.store import cache
from config import settings
from handlers import command as cmd_handler
from handlers import memo as memo_handler
from handlers import callback as cb_handler

router = APIRouter()


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    if x_telegram_bot_api_secret_token != settings.telegram_secret_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()

    # 중복 메시지 제거
    update_id = update.get("update_id", 0)
    if cache.is_duplicate(update_id):
        return {"ok": True}

    # ── callback_query (인라인 버튼 클릭) ──────────────────────────────────────
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id: int = cq["message"]["chat"]["id"]
        message_id: int = cq["message"]["message_id"]
        background_tasks.add_task(
            cb_handler.handle_callback,
            chat_id,
            cq["id"],
            cq.get("data", ""),
            message_id,
        )
        return {"ok": True}

    # ── 일반 메시지 ───────────────────────────────────────────────────────────
    message = update.get("message", {})
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text: str = message.get("text", "").strip()

    if not chat_id or not text:
        return {"ok": True}

    pending = cache.get_pending(chat_id)

    # 프로젝트 설명 입력 대기 상태 (신규 추가 시)
    if (
        pending
        and pending.get("mode") == "awaiting_project_desc"
        and not text.startswith("/")
    ):
        background_tasks.add_task(
            cmd_handler.handle_project_desc_input, chat_id, text, pending
        )
        return {"ok": True}

    # 프로젝트 설명 수정 대기 상태 (기존 프로젝트 /desc 명령 후)
    if (
        pending
        and pending.get("mode") == "awaiting_desc_update"
        and not text.startswith("/")
    ):
        background_tasks.add_task(
            cmd_handler.handle_desc_update_input, chat_id, text, pending
        )
        return {"ok": True}

    # '기타 입력' 후 프로젝트명 직접 입력 대기 상태
    if (
        pending
        and pending.get("mode") == "awaiting_project_text"
        and not text.startswith("/")
    ):
        background_tasks.add_task(
            memo_handler.handle_project_text_input, chat_id, text, pending
        )
        return {"ok": True}

    # /cancel 명령 — pending 컨텍스트 정리
    if text.lower().startswith("/cancel"):
        if pending:
            cache.clear_pending(chat_id)
            from services import telegram
            background_tasks.add_task(
                telegram.send_message, chat_id, "진행 중인 분류가 취소됐어요."
            )
        else:
            from services import telegram
            background_tasks.add_task(
                telegram.send_message, chat_id, "취소할 항목이 없어요."
            )
        return {"ok": True}

    # 일반 명령어
    if text.startswith("/"):
        background_tasks.add_task(cmd_handler.handle_command, chat_id, text)
        return {"ok": True}

    # 메모 처리
    background_tasks.add_task(memo_handler.handle_memo, chat_id, text)
    return {"ok": True}
