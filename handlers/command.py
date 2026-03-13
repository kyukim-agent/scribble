from services import notion, telegram


async def handle_command(chat_id: int, text: str) -> None:
    parts = text.strip().split(maxsplit=2)
    cmd = parts[0].lower().split("@")[0]  # strip bot username suffix if present

    if cmd == "/help":
        await telegram.send_message(
            chat_id,
            "📌 <b>Scribble 명령어</b>\n\n"
            "/projects — 프로젝트 목록 조회\n"
            "/add [이름] — 프로젝트 추가\n"
            "/del [이름] — 프로젝트 삭제\n"
            "/rename [구이름] [새이름] — 이름 변경\n"
            "/cancel — 진행 중인 분류 취소\n"
            "/help — 이 도움말",
        )

    elif cmd == "/projects":
        projects = await notion.get_active_projects()
        active = [p for p in projects if p != "Uncategorized"]
        if active:
            lines = "\n".join(f"• {p}" for p in active)
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
        success = await notion.add_project(name)
        if success:
            await telegram.send_message(chat_id, f"✅ '{name}' 프로젝트가 추가됐어요!")
        else:
            await telegram.send_message(chat_id, f"이미 '{name}' 프로젝트가 있어요.")

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
