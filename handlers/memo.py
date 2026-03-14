from services import llm, notion, telegram
from cache.store import cache


def _build_project_buttons(
    confidence: str,
    project: str | None,
    candidates: list[str],
    all_projects: list[dict],
) -> tuple[list[list[dict]], str]:
    """인라인 키보드 버튼과 질문 메시지를 구성합니다."""
    all_names = [p["name"] for p in all_projects]
    if confidence == "medium":
        button_projects: list[str] = []
        if project:
            button_projects.append(project)
        for c in candidates:
            if c not in button_projects:
                button_projects.append(c)
        button_projects = button_projects[:3]
        question = f"📁 '{project}'로 저장할까요? 다른 프로젝트를 선택할 수도 있어요."
    else:  # low
        button_projects = [c for c in candidates if c][:5]
        question = "어떤 프로젝트로 저장할까요?"

    buttons = [[{"text": p, "callback_data": f"project:{p}"}] for p in button_projects]
    buttons.append([{"text": "📂 Uncategorized", "callback_data": "project:Uncategorized"}])

    # 표시 안 된 프로젝트가 있으면 '기타 입력' 추가
    shown = set(button_projects) | {"Uncategorized"}
    if any(p not in shown for p in all_names):
        buttons.append([{"text": "✏️ 기타 입력", "callback_data": "project:__other__"}])

    return buttons, question


async def handle_memo(chat_id: int, text: str) -> None:
    if not text.strip():
        await telegram.send_message(chat_id, "💬 메모 내용을 입력해주세요.")
        return

    # Pending 충돌 처리
    existing = cache.get_pending(chat_id)
    if existing:
        r = existing["llm_result"]
        await notion.save_memo(
            raw_text=existing["memo_text"],
            project="Uncategorized",
            tags=r.get("tags", []),
            title=r.get("title", existing["memo_text"][:50]),
            bullets=r.get("bullets", []),
            corrected=r.get("corrected", existing["memo_text"]),
        )
        cache.clear_pending(chat_id)
        await telegram.send_message(chat_id, "이전 메모가 Uncategorized로 저장됐어요.")

    projects = await notion.get_active_projects()  # list[dict]
    result = await llm.process_memo(text, projects)

    if result is None:
        saved = await notion.save_memo(
            raw_text=text,
            project="Uncategorized",
            tags=[],
            title=text[:50],
            bullets=[],
            corrected=text,
        )
        msg = (
            "⚠️ AI 처리 중 오류가 발생했어요. 메모는 원문으로 Uncategorized에 저장됐어요."
            if saved
            else "❌ 저장에 실패했어요. 잠시 후 다시 시도해주세요."
        )
        await telegram.send_message(chat_id, msg)
        return

    confidence = result.get("confidence", "low")
    project = result.get("project")

    if confidence == "high" and project:
        saved = await notion.save_memo(
            raw_text=text,
            project=project,
            tags=result.get("tags", []),
            title=result.get("title", ""),
            bullets=result.get("bullets", []),
            corrected=result.get("corrected", text),
        )
        if saved:
            await telegram.send_message(
                chat_id, f"✅ 메모가 저장됐어요!\n\n📁 프로젝트: {project}"
            )
        else:
            await telegram.send_message(
                chat_id, "❌ 저장에 실패했어요. 잠시 후 다시 시도해주세요."
            )
        return

    # medium / low → 사용자 확인 요청
    buttons, question = _build_project_buttons(
        confidence, project, result.get("candidates", []), projects
    )
    msg_id = await telegram.send_inline_keyboard(chat_id, question, buttons)
    cache.set_pending(
        chat_id,
        {
            "memo_text": text,
            "llm_result": result,
            "question_message_id": msg_id,
            "mode": "awaiting_project_button",
        },
    )


async def handle_project_text_input(
    chat_id: int, project_name: str, pending: dict
) -> None:
    """'기타 입력' 후 사용자가 직접 타이핑한 프로젝트명으로 저장합니다."""
    r = pending["llm_result"]
    saved = await notion.save_memo(
        raw_text=pending["memo_text"],
        project=project_name,
        tags=r.get("tags", []),
        title=r.get("title", ""),
        bullets=r.get("bullets", []),
        corrected=r.get("corrected", pending["memo_text"]),
    )
    cache.clear_pending(chat_id)

    if saved:
        await telegram.send_message(
            chat_id, f"✅ 메모가 저장됐어요!\n\n📁 프로젝트: {project_name}"
        )
    else:
        await telegram.send_message(
            chat_id, "❌ 저장에 실패했어요. 잠시 후 다시 시도해주세요."
        )
