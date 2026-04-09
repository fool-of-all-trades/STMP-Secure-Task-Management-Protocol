from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from server.security.security_config import (
    RATE_LIMIT_BAN_SECONDS,
    RATE_LIMIT_MAX_VIOLATIONS,
    RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_PER_SECOND,
    RATE_LIMIT_VIOLATION_WINDOW_SECONDS,
)


class InMemoryRateLimiter:
    def __init__(
        self,
        per_second_limit: int = RATE_LIMIT_PER_SECOND,
        per_minute_limit: int = RATE_LIMIT_PER_MINUTE,
        ban_seconds: int = RATE_LIMIT_BAN_SECONDS,
        max_violations: int = RATE_LIMIT_MAX_VIOLATIONS,
        violation_window_seconds: int = RATE_LIMIT_VIOLATION_WINDOW_SECONDS,
    ) -> None:
        self.per_second_limit = per_second_limit
        self.per_minute_limit = per_minute_limit
        self.ban_seconds = ban_seconds
        self.max_violations = max_violations
        self.violation_window_seconds = violation_window_seconds

        self._events: dict[str, deque] = defaultdict(deque)
        self._violations: dict[str, deque] = defaultdict(deque)
        self._blocked_until: dict[str, datetime] = {}

    def _prune(self, scope_key: str, now: datetime) -> None:
        one_minute_ago = now - timedelta(minutes=1)
        violation_cutoff = now - timedelta(seconds=self.violation_window_seconds)

        events = self._events[scope_key]
        while events and events[0] <= one_minute_ago:
            events.popleft()

        violations = self._violations[scope_key]
        while violations and violations[0] <= violation_cutoff:
            violations.popleft()

        blocked_until = self._blocked_until.get(scope_key)
        if blocked_until is not None and blocked_until <= now:
            del self._blocked_until[scope_key]

    def _count_last_second(self, scope_key: str, now: datetime) -> int:
        one_second_ago = now - timedelta(seconds=1)
        return sum(1 for event_time in self._events[scope_key] if event_time > one_second_ago)

    def check_and_record(self, scope_key: str, now: datetime | None = None) -> dict:
        scope_key = scope_key.strip() if isinstance(scope_key, str) else ""
        if not scope_key:
            return {"ok": False, "error_code": 103, "message": "Missing rate limit scope"}

        current_time = now or datetime.now(timezone.utc)
        self._prune(scope_key, current_time)

        blocked_until = self._blocked_until.get(scope_key)
        if blocked_until is not None and blocked_until > current_time:
            retry_after = max(1, int((blocked_until - current_time).total_seconds()))
            return {
                "ok": False,
                "error_code": 400,
                "message": "Rate limit exceeded",
                "temporarily_blocked": True,
                "retry_after_seconds": retry_after,
            }

        last_second_count = self._count_last_second(scope_key, current_time)
        last_minute_count = len(self._events[scope_key])

        if last_second_count >= self.per_second_limit or last_minute_count >= self.per_minute_limit:
            self._violations[scope_key].append(current_time)
            temporarily_blocked = False

            if len(self._violations[scope_key]) >= self.max_violations:
                blocked_until = current_time + timedelta(seconds=self.ban_seconds)
                self._blocked_until[scope_key] = blocked_until
                temporarily_blocked = True

            retry_after_seconds = 1 if last_second_count >= self.per_second_limit else 60
            if temporarily_blocked:
                retry_after_seconds = self.ban_seconds

            return {
                "ok": False,
                "error_code": 400,
                "message": "Rate limit exceeded",
                "temporarily_blocked": temporarily_blocked,
                "retry_after_seconds": retry_after_seconds,
            }

        self._events[scope_key].append(current_time)

        return {
            "ok": True,
            "scope_key": scope_key,
            "requests_last_second": last_second_count + 1,
            "requests_last_minute": last_minute_count + 1,
        }

    def reset_scope(self, scope_key: str) -> None:
        self._events.pop(scope_key, None)
        self._violations.pop(scope_key, None)
        self._blocked_until.pop(scope_key, None)


_default_rate_limiter = InMemoryRateLimiter()



def check_rate_limit(scope_key: str, now: datetime | None = None) -> dict:
    return _default_rate_limiter.check_and_record(scope_key, now=now)



def reset_rate_limit_scope(scope_key: str) -> None:
    _default_rate_limiter.reset_scope(scope_key)
