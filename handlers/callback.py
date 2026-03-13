from services import notion, telegram
from cache.store import cache


async def handle_callback(
    chat_id: int, callback_query_id: str, data: str, message_id: int
) -> None:
    await telegram.answer_callback_query(callback_query_id)

    # ── 프로젝트 삭제 확인/취소 ───────────────────────────────────────────────

    if data.startswith("del_confirm:"):
        name = data[len("del_confirm:"):]
        await telegram.remove_inline_keyboard(chat_id, message_id)
        success = await notion.delete_project(name)
        if success:
            await telegram.send_message(
                chat_id, f"🗑 '{name}' 프로젝트가 삭제됐어요."
            )
        else:
            await telegram.send_message(
                chat_id,
                f"❌ '{name}'은 삭제할 수 없어요. (존재하지 않거나 시스템 프로젝트입니다)",
            )
        return

    if data.startswith("del_cancel:"):
        await telegram.remove_inline_keyboard(chat_id, message_id)
        await telegram.send_message(chat_id, "취소됐어요.")
        return

    # ── 프로젝트 선택 ──────────────────────────────────────────────────────────

    if data.startswith("project:"):
        selected = data[len("project:"):]

        pending = cache.get_pending(chat_id)
        if not pending:
            await telegram.remove_inline_keyboard(chat_id, message_id)
            await telegram.send_message(
                chat_id,
                "⏰ 컨텍스트가 만료됐어요. 다시 메모를 전송해주세요.",
            )
            return

        await telegram.remove_inline_keyboard(chat_id, message_id)

        if selected == "__other__":
            cache.set_pending(chat_id, {**pending, "mode": "awaiting_project_text"})
            await telegram.send_message(
                chat_id, "저장할 프로젝트 이름을 직접 입력해주세요."
            )
            return

        r = pending["llm_result"]
        saved = await notion.save_memo(
            raw_text=pending["memo_text"],
            project=selected,
            tags=r.get("tags", []),
            title=r.get("title", ""),
            bullets=r.get("bullets", []),
            corrected=r.get("corrected", pending["memo_text"]),
        )
        cache.clear_pending(chat_id)

        if saved:
            await telegram.send_message(
                chat_id, f"✅ 메모가 저장됐어요!\n\n📁 프로젝트: {selected}"
            )
        else:
            await telegram.send_message(
                chat_id, "❌ 저장에 실패했어요. 잠시 후 다시 시도해주세요."
            )
