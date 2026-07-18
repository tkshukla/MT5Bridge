import pytest
from fastapi import HTTPException

from app.security import Role, create_access_token, decode_token, hash_api_key


def test_access_token_roundtrip():
    token = create_access_token("mt5-desktop-1", Role.TRADER)
    principal = decode_token(token)
    assert principal.subject == "mt5-desktop-1"
    assert principal.role == Role.TRADER


def test_decode_rejects_garbage_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not-a-real-jwt")
    assert exc_info.value.status_code == 401


def test_hash_api_key_is_sha256_hex():
    digest = hash_api_key("supersecret")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


@pytest.mark.parametrize(
    ("role", "expected_rank_ge_viewer"),
    [(Role.VIEWER, True), (Role.TRADER, True), (Role.ADMIN, True)],
)
def test_all_roles_at_least_viewer_rank(role, expected_rank_ge_viewer):
    from app.security import _ROLE_RANK

    assert (_ROLE_RANK[role] >= _ROLE_RANK[Role.VIEWER]) == expected_rank_ge_viewer
