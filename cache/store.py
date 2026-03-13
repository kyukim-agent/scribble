import time
from typing import Optional


PENDING_TTL = 300  # 5 minutes


class CacheStore:
    def __init__(self):
        self._pending: dict[int, dict] = {}
        self._projects: Optional[list[str]] = None
        self._processed_updates: set[int] = set()

    # ── Update deduplication ──────────────────────────────────────────────────

    def is_duplicate(self, update_id: int) -> bool:
        if update_id in self._processed_updates:
            return True
        if len(self._processed_updates) > 200:
            self._processed_updates.clear()
        self._processed_updates.add(update_id)
        return False

    # ── Pending context ───────────────────────────────────────────────────────

    def get_pending(self, chat_id: int) -> Optional[dict]:
        ctx = self._pending.get(chat_id)
        if ctx is None:
            return None
        if ctx["expires_at"] > time.time():
            return ctx
        del self._pending[chat_id]
        return None

    def set_pending(self, chat_id: int, data: dict):
        self._pending[chat_id] = {
            **data,
            "expires_at": time.time() + PENDING_TTL,
        }

    def clear_pending(self, chat_id: int):
        self._pending.pop(chat_id, None)

    def get_all_expired_pending(self) -> list[tuple[int, dict]]:
        now = time.time()
        expired = [
            (chat_id, ctx)
            for chat_id, ctx in list(self._pending.items())
            if ctx["expires_at"] <= now
        ]
        for chat_id, _ in expired:
            del self._pending[chat_id]
        return expired

    # ── Project list cache ────────────────────────────────────────────────────

    def get_projects(self) -> Optional[list[str]]:
        return self._projects

    def set_projects(self, projects: list[str]):
        self._projects = projects

    def invalidate_projects(self):
        self._projects = None


cache = CacheStore()
