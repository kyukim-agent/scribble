import asyncio
from cache.store import cache


async def cleanup_expired_pending() -> None:
    """만료된 pending 메모를 주기적으로 Uncategorized에 저장합니다."""
    while True:
        await asyncio.sleep(60)  # 1분마다 체크

        expired = cache.get_all_expired_pending()
        if not expired:
            continue

        from services import notion, telegram

        for chat_id, ctx in expired:
            r = ctx.get("llm_result", {})
            await notion.save_memo(
                raw_text=ctx["memo_text"],
                project="Uncategorized",
                tags=r.get("tags", []),
                title=r.get("title", ctx["memo_text"][:50]),
                bullets=r.get("bullets", []),
                corrected=r.get("corrected", ctx["memo_text"]),
            )
            await telegram.send_message(
                chat_id,
                "⏰ 응답 시간이 초과되어 'Uncategorized'로 저장했어요.",
            )
