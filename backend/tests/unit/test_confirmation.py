from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.confirmation import assert_confirmation_fresh, hash_confirmation_token


def test_hash_is_deterministic_and_distinct():
    assert hash_confirmation_token("abc") == hash_confirmation_token("abc")
    assert hash_confirmation_token("abc") != hash_confirmation_token("abd")


def test_fresh_confirmation_within_ttl_passes():
    assert_confirmation_fresh(datetime.now(timezone.utc) - timedelta(seconds=5))


def test_stale_confirmation_beyond_ttl_rejected():
    with pytest.raises(HTTPException) as exc_info:
        assert_confirmation_fresh(datetime.now(timezone.utc) - timedelta(seconds=999))
    assert exc_info.value.status_code == 422


def test_future_confirmed_at_rejected():
    with pytest.raises(HTTPException):
        assert_confirmation_fresh(datetime.now(timezone.utc) + timedelta(seconds=10))


def test_naive_datetime_treated_as_utc():
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    assert_confirmation_fresh(naive_now)
