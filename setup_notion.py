"""
Notion 데이터베이스 프로퍼티 초기화 스크립트

실행:
  python setup_notion.py

두 DB의 스키마를 코드와 일치하도록 생성/업데이트합니다.
이미 존재하는 프로퍼티는 덮어쓰지 않습니다.
"""

import httpx
from dotenv import load_dotenv
from config import settings

load_dotenv()

HEADERS = {
    "Authorization": f"Bearer {settings.notion_api_key}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def patch_database(db_id: str, properties: dict, label: str) -> None:
    resp = httpx.patch(
        f"https://api.notion.com/v1/databases/{db_id}",
        headers=HEADERS,
        json={"properties": properties},
        timeout=15.0,
    )
    if resp.status_code == 200:
        print(f"✅ {label} 업데이트 완료")
    else:
        print(f"❌ {label} 실패: {resp.status_code} {resp.text}")


# ── Scribble Index DB ─────────────────────────────────────────────────────────

SCRIBBLE_PROPERTIES = {
    "Project":    {"select": {}},
    "Tags":       {"multi_select": {}},
    "Created At": {"date": {}},
    "Source":     {"select": {}},
    "Status":     {"select": {}},
    "Raw Memo":   {"rich_text": {}},
    "Structured": {"rich_text": {}},
}

# ── Project Registry DB ───────────────────────────────────────────────────────

PROJECT_PROPERTIES = {
    "Active":      {"checkbox": {}},
    "Is System":   {"checkbox": {}},
    "Created At":  {"date": {}},
    "Description": {"rich_text": {}},
}


if __name__ == "__main__":
    print("=== Scribble Index DB ===")
    patch_database(settings.notion_scribble_db_id, SCRIBBLE_PROPERTIES, "Scribble Index DB")

    print("\n=== Project Registry DB ===")
    patch_database(settings.notion_project_db_id, PROJECT_PROPERTIES, "Project Registry DB")

    print("\n완료! Notion에서 DB 스키마를 확인해주세요.")
