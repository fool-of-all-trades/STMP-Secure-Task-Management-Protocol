from datetime import datetime, timedelta, timezone

from server.services.rate_limit_service import InMemoryRateLimiter



def test_rate_limiter_allows_requests_within_limits():
    limiter = InMemoryRateLimiter(per_second_limit=3, per_minute_limit=5, ban_seconds=30)
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

    result_1 = limiter.check_and_record("session:test", now=now)
    result_2 = limiter.check_and_record("session:test", now=now + timedelta(milliseconds=200))
    result_3 = limiter.check_and_record("session:test", now=now + timedelta(milliseconds=400))

    assert result_1["ok"] is True
    assert result_2["ok"] is True
    assert result_3["ok"] is True



def test_rate_limiter_blocks_when_per_second_limit_is_exceeded():
    limiter = InMemoryRateLimiter(per_second_limit=2, per_minute_limit=10, ban_seconds=30)
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

    assert limiter.check_and_record("session:test", now=now)["ok"] is True
    assert limiter.check_and_record("session:test", now=now + timedelta(milliseconds=100))["ok"] is True

    blocked = limiter.check_and_record("session:test", now=now + timedelta(milliseconds=200))

    assert blocked["ok"] is False
    assert blocked["error_code"] == 400
    assert blocked["temporarily_blocked"] is False



def test_rate_limiter_blocks_when_per_minute_limit_is_exceeded():
    limiter = InMemoryRateLimiter(per_second_limit=10, per_minute_limit=3, ban_seconds=30)
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

    assert limiter.check_and_record("session:test", now=now)["ok"] is True
    assert limiter.check_and_record("session:test", now=now + timedelta(seconds=10))["ok"] is True
    assert limiter.check_and_record("session:test", now=now + timedelta(seconds=20))["ok"] is True

    blocked = limiter.check_and_record("session:test", now=now + timedelta(seconds=30))

    assert blocked["ok"] is False
    assert blocked["error_code"] == 400



def test_rate_limiter_temporarily_blocks_after_repeated_violations():
    limiter = InMemoryRateLimiter(
        per_second_limit=1,
        per_minute_limit=10,
        ban_seconds=120,
        max_violations=3,
        violation_window_seconds=120,
    )
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

    assert limiter.check_and_record("session:test", now=now)["ok"] is True
    assert limiter.check_and_record("session:test", now=now + timedelta(milliseconds=100))["ok"] is False
    assert limiter.check_and_record("session:test", now=now + timedelta(milliseconds=200))["ok"] is False

    blocked = limiter.check_and_record("session:test", now=now + timedelta(milliseconds=300))
    still_blocked = limiter.check_and_record("session:test", now=now + timedelta(seconds=30))
    after_ban = limiter.check_and_record("session:test", now=now + timedelta(seconds=121))

    assert blocked["ok"] is False
    assert blocked["temporarily_blocked"] is True
    assert still_blocked["ok"] is False
    assert still_blocked["temporarily_blocked"] is True
    assert after_ban["ok"] is True
