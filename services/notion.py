import httpx
import logging
from datetime import datetime, timezone
from config import settings
from cache.store import cache

logger = logging.getLogger(__name__)

_NOTION_VERSION = "2022-06-28"
_HEADERS = {
    "Authorization": f"Bearer {settings.notion_api_key}",
    "Content-Type": "application/json",
    "Notion-Version": _NOTION_VERSION,
}
_BASE = "https://api.notion.com/v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Project Registry DB ───────────────────────────────────────────────────────


async def get_active_projects() -> list[dict]:
    """Active 프로젝트 목록을 [{name, description}, ...] 형태로 반환합니다."""
    cached = cache.get_projects()
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/databases/{settings.notion_project_db_id}/query",
                headers=_HEADERS,
                json={"filter": {"property": "Active", "checkbox": {"equals": True}}},
                timeout=10.0,
            )
            data = resp.json()
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.error("Notion get_active_projects network error: %s", e)
        return []

    projects: list[dict] = []
    for page in data.get("results", []):
        title_parts = page["properties"]["Name"]["title"]
        if not title_parts:
            continue
        name = title_parts[0]["text"]["content"]
        desc_parts = page["properties"].get("Description", {}).get("rich_text", [])
        description = desc_parts[0]["text"]["content"] if desc_parts else ""
        projects.append({"name": name, "description": description})

    cache.set_projects(projects)
    return projects


async def ensure_uncategorized() -> None:
    """서버 기동 시 Uncategorized 프로젝트가 없으면 생성합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/databases/{settings.notion_project_db_id}/query",
            headers=_HEADERS,
            json={
                "filter": {
                    "property": "Name",
                    "title": {"equals": "Uncategorized"},
                }
            },
            timeout=10.0,
        )
        data = resp.json()
        if not data.get("results"):
            await client.post(
                f"{_BASE}/pages",
                headers=_HEADERS,
                json={
                    "parent": {"database_id": settings.notion_project_db_id},
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Uncategorized"}}]},
                        "Active": {"checkbox": True},
                        "Is System": {"checkbox": True},
                        "Created At": {"date": {"start": _now_iso()}},
                    },
                },
                timeout=10.0,
            )

    cache.invalidate_projects()


async def add_project(name: str, description: str = "") -> bool:
    """프로젝트를 추가합니다. 이미 존재하면 False를 반환합니다."""
    projects = await get_active_projects()
    if any(p["name"] == name for p in projects):
        return False

    properties: dict = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Active": {"checkbox": True},
        "Is System": {"checkbox": False},
        "Created At": {"date": {"start": _now_iso()}},
    }
    if description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description[:2000]}}]
        }

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{_BASE}/pages",
            headers=_HEADERS,
            json={
                "parent": {"database_id": settings.notion_project_db_id},
                "properties": properties,
            },
            timeout=10.0,
        )

    cache.invalidate_projects()
    return True


async def delete_project(name: str) -> bool:
    """Active=False로 소프트 삭제합니다. 시스템 프로젝트나 미존재 시 False를 반환합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/databases/{settings.notion_project_db_id}/query",
            headers=_HEADERS,
            json={"filter": {"property": "Name", "title": {"equals": name}}},
            timeout=10.0,
        )
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return False

        page = results[0]
        if page["properties"].get("Is System", {}).get("checkbox"):
            return False

        await client.patch(
            f"{_BASE}/pages/{page['id']}",
            headers=_HEADERS,
            json={"properties": {"Active": {"checkbox": False}}},
            timeout=10.0,
        )

    cache.invalidate_projects()
    return True


async def update_project_description(name: str, description: str) -> bool:
    """기존 프로젝트의 Description을 업데이트합니다. 미존재 시 False를 반환합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/databases/{settings.notion_project_db_id}/query",
            headers=_HEADERS,
            json={"filter": {"property": "Name", "title": {"equals": name}}},
            timeout=10.0,
        )
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return False

        page_id = results[0]["id"]
        await client.patch(
            f"{_BASE}/pages/{page_id}",
            headers=_HEADERS,
            json={
                "properties": {
                    "Description": {
                        "rich_text": [{"text": {"content": description[:2000]}}]
                    }
                }
            },
            timeout=10.0,
        )

    cache.invalidate_projects()
    return True


async def rename_project(old_name: str, new_name: str) -> bool:
    """프로젝트 이름을 변경합니다. 미존재 시 False를 반환합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/databases/{settings.notion_project_db_id}/query",
            headers=_HEADERS,
            json={"filter": {"property": "Name", "title": {"equals": old_name}}},
            timeout=10.0,
        )
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return False

        page = results[0]
        await client.patch(
            f"{_BASE}/pages/{page['id']}",
            headers=_HEADERS,
            json={
                "properties": {
                    "Name": {"title": [{"text": {"content": new_name}}]}
                }
            },
            timeout=10.0,
        )

    cache.invalidate_projects()
    return True


# ── Scribble Index DB ─────────────────────────────────────────────────────────


async def save_memo(
    raw_text: str,
    project: str,
    tags: list[str],
    title: str,
    bullets: list[str],
    corrected: str,
) -> bool:
    structured = "\n".join(f"• {b}" for b in bullets)
    if len(structured) > 2000:
        structured = structured[:1997] + "..."

    properties = {
        "Name": {"title": [{"text": {"content": (title or raw_text)[:200]}}]},
        "Project": {"select": {"name": project}},
        "Tags": {"multi_select": [{"name": t} for t in tags[:5]]},
        "Created At": {"date": {"start": _now_iso()}},
        "Source": {"select": {"name": "Telegram"}},
        "Status": {"select": {"name": "Saved"}},
        "Raw Memo": {"rich_text": [{"text": {"content": raw_text[:2000]}}]},
        "Structured": {"rich_text": [{"text": {"content": structured}}]},
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/pages",
                headers=_HEADERS,
                json={
                    "parent": {"database_id": settings.notion_scribble_db_id},
                    "properties": properties,
                },
                timeout=15.0,
            )
            if resp.status_code not in (200, 201):
                logger.error("Notion save_memo failed: status=%s body=%s", resp.status_code, resp.text)
                return False
            return True
    except Exception as e:
        logger.exception("Notion save_memo exception: %s", e)
        return False
