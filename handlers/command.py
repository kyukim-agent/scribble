from services import notion, telegram
from cache.store import cache


async def handle_command(chat_id: int, text: str) -> None:
    parts = text.strip().split(maxsplit=2)
    cmd = parts[0].lower().split("@")[0]  # strip bot username suffix if present

    if cmd == "/help":
        await telegram.send_message(
            chat_id,
            "📌 <b>Scribble 명령어</b>\n\n"
            "/projects — 프로젝트 목록 조회\n"
            "/add [이름] — 프로젝트 추가 (설명 입력 안내)\n"
            "/desc [이름] — 프로젝트 설명 추가/수정\n"
            "/del [이름] — 프로젝트 삭제\n"
            "/rename [구이름] [새이름] — 이름 변경\n"
            "/cancel — 진행 중인 분류 취소\n"
            "/help — 이 도움말",
        )

    elif cmd == "/projects":
        projects = await notion.get_active_projects()
        active = [p for p in projects if p["name"] != "Uncategorized"]
        if active:
            lines = "\n".join(
                f"• {p['name']}" + (f" — {p['description']}" if p.get("description") else "")
                for p in active
            )
            await telegram.send_message(
                chat_id, f"📋 현재 프로젝트 ({len(active)}개):\n{lines}"
            )
        else:
            await telegram.send_message(
                chat_id,
                "📋 등록된 프로젝트가 없어요.\n/add [이름] 으로 추가해보세요.",
            )

    elif cmd == "/add":
        if len(parts) < 2:
            await telegram.send_message(chat_id, "사용법: /add [프로젝트 이름]")
            return
        name = parts[1]
        # 이미 존재하는지 확인
        projects = await notion.get_active_projects()
        if any(p["name"] == name for p in projects):
            await telegram.send_message(chat_id, f"이미 '{name}' 프로젝트가 있어요.")
            return
        # description 입력 요청
        cache.set_pending(chat_id, {"mode": "awaiting_project_desc", "project_name": name})
        await telegram.send_message(
            chat_id,
            f"📝 '{name}' 프로젝트의 배경/내용을 간략히 입력해주세요.\n"
            f"(예: 어떤 목적, 어떤 주제의 프로젝트인지)\n\n"
            f"건너뛰려면 <b>skip</b> 을 입력하세요.",
        )

    elif cmd == "/desc":
        if len(parts) < 2:
            await telegram.send_message(chat_id, "사용법: /desc [프로젝트 이름]")
            return
        name = parts[1]
        projects = await notion.get_active_projects()
        matched = next((p for p in projects if p["name"] == name), None)
        if not matched:
            await telegram.send_message(chat_id, f"❌ '{name}' 프로젝트를 찾을 수 없어요.")
            return
        current_desc = matched.get("description", "").strip()
        desc_preview = f"\n\n현재 설명: {current_desc}" if current_desc else "\n\n(아직 설명이 없어요)"
        cache.set_pending(chat_id, {"mode": "awaiting_desc_update", "project_name": name})
        await telegram.send_message(
            chat_id,
            f"📝 <b>{name}</b> 프로젝트{desc_preview}\n\n"
            f"새 설명을 입력해주세요.",
        )

    elif cmd == "/del":
        if len(parts) < 2:
            await telegram.send_message(chat_id, "사용법: /del [프로젝트 이름]")
            return
        name = parts[1]
        buttons = [
            [
                {"text": "✅ 확인", "callback_data": f"del_confirm:{name}"},
                {"text": "❌ 취소", "callback_data": f"del_cancel:{name}"},
            ]
        ]
        await telegram.send_inline_keyboard(
            chat_id,
            f"⚠️ '{name}' 프로젝트를 삭제할까요?\n기존 메모는 그대로 유지됩니다.",
            buttons,
        )

    elif cmd == "/rename":
        if len(parts) < 3:
            await telegram.send_message(
                chat_id, "사용법: /rename [구이름] [새이름]"
            )
            return
        old, new = parts[1], parts[2]
        success = await notion.rename_project(old, new)
        if success:
            await telegram.send_message(
                chat_id,
                f"✅ '{old}' → '{new}' 이름이 변경됐어요!\n기존 메모의 프로젝트명은 유지됩니다.",
            )
        else:
            await telegram.send_message(
                chat_id, f"❌ '{old}' 프로젝트를 찾을 수 없어요."
            )

    else:
        await telegram.send_message(
            chat_id, "알 수 없는 명령어예요. /help 로 도움말을 확인해주세요."
        )


async def handle_project_desc_input(
    chat_id: int, text: str, pending: dict
) -> None:
    """프로젝트 description 입력 대기 상태에서 사용자 입력을 처리합니다."""
    name = pending.get("project_name", "")
    cache.clear_pending(chat_id)

    description = "" if text.strip().lower() == "skip" else text.strip()
    success = await notion.add_project(name, description)

    if success:
        desc_preview = f"\n\ud83d\udcc4 설명: {description}" if description else ""
        await telegram.send_message(
            chat_id,
            f"\u2705 '{name}' 프로젝트가 추가됐어요!{desc_preview}",
        )
    else:
        await telegram.send_message(chat_id, f"이미 '{name}' 프로젝트가 있어요.")


async def handle_desc_update_input(
    chat_id: int, text: str, pending: dict
) -> None:
    """기존 프로젝트의 description 수정 대기 상태에서 사용자 입력을 처리합니다."""
    name = pending.get("project_name", "")
    cache.clear_pending(chat_id)

    description = text.strip()
    success = await notion.update_project_description(name, description)

    if success:
        await telegram.send_message(
            chat_id,
            f"\u2705 <b>{name}</b> 프로젝트 설명이 업데이트됐어요!\n\n"
            f"\ud83d\udcc4 {description}",
        )
    else:
        await telegram.send_message(chat_id, f"❌ '{name}' 프로젝트를 찾을 수 없어요.")
