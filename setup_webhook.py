"""
Telegram Webhook 등록 스크립트

Railway 배포 후 아래 명령으로 한 번만 실행하세요:
  python setup_webhook.py https://your-app.up.railway.app

등록된 웹훅 확인:
  python setup_webhook.py --info

웹훅 삭제:
  python setup_webhook.py --delete

봇 커맨드만 재등록:
  python setup_webhook.py --commands
"""

import sys
import httpx
from dotenv import load_dotenv
from config import settings

load_dotenv()


def set_webhook(url: str) -> None:
    webhook_url = f"{url}/webhook/telegram"
    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token}/setWebhook",
        json={
            "url": webhook_url,
            "secret_token": settings.telegram_secret_token,
            "allowed_updates": ["message", "callback_query"],
        },
    )
    data = resp.json()
    if data.get("ok"):
        print(f"✅ 웹훅 등록 완료: {webhook_url}")
        set_commands()
    else:
        print(f"❌ 실패: {data}")


def get_webhook_info() -> None:
    resp = httpx.get(
        f"https://api.telegram.org/bot{settings.telegram_token}/getWebhookInfo"
    )
    data = resp.json()
    info = data.get("result", {})
    print(f"URL      : {info.get('url', '(없음)')}")
    print(f"Pending  : {info.get('pending_update_count', 0)}")
    print(f"Last err : {info.get('last_error_message', '없음')}")


def delete_webhook() -> None:
    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token}/deleteWebhook"
    )
    data = resp.json()
    if data.get("ok"):
        print("✅ 웹훅 삭제 완료")
    else:
        print(f"❌ 실패: {data}")


BOT_COMMANDS = [
    {"command": "projects", "description": "프로젝트 목록 조회"},
    {"command": "add",      "description": "프로젝트 추가 (설명 입력 안내)"},
    {"command": "desc",     "description": "프로젝트 설명 추가/수정"},
    {"command": "del",      "description": "프로젝트 삭제"},
    {"command": "rename",   "description": "프로젝트 이름 변경"},
    {"command": "cancel",   "description": "진행 중인 분류 취소"},
    {"command": "help",     "description": "도움말"},
]


def set_commands() -> None:
    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token}/setMyCommands",
        json={"commands": BOT_COMMANDS},
    )
    data = resp.json()
    if data.get("ok"):
        print("✅ 봇 커맨드 등록 완료")
        for c in BOT_COMMANDS:
            print(f"   /{c['command']} — {c['description']}")
    else:
        print(f"❌ 커맨드 등록 실패: {data}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--info":
        get_webhook_info()
    elif args[0] == "--delete":
        delete_webhook()
    elif args[0] == "--commands":
        set_commands()
    else:
        set_webhook(args[0].rstrip("/"))
