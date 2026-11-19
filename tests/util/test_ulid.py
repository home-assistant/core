"""Test Home Assistant ulid util methods."""

from unittest.mock import patch
import uuid

from homeassistant.util import ulid as ulid_util


async def test_ulid_util_uuid_hex() -> None:
    """Verify we can generate a ulid in hex."""
    assert len(ulid_util.ulid_hex()) == 32
    assert uuid.UUID(ulid_util.ulid_hex())


async def test_ulid_util_uuid() -> None:
    """Verify we can generate a ulid."""
    assert len(ulid_util.ulid()) == 26


async def test_secure_ulid_now() -> None:
    """Verify a secure ulid has the current timestamp and secrets randomness."""
    with (
        patch(
            "homeassistant.util.ulid.time.time_ns",
            return_value=1_700_000_000_123_456_789,
        ),
        patch(
            "homeassistant.util.ulid.secrets.token_bytes", return_value=b"\xab" * 10
        ) as mock_token_bytes,
    ):
        ulid = ulid_util.secure_ulid_now()

    mock_token_bytes.assert_called_once_with(10)
    assert len(ulid) == 26
    ulid_bytes = ulid_util.ulid_to_bytes(ulid)
    assert int.from_bytes(ulid_bytes[:6]) == 1_700_000_000_123
    assert ulid_bytes[6:] == b"\xab" * 10


async def test_secure_ulid_now_is_unique() -> None:
    """Verify two secure ulids differ."""
    assert ulid_util.secure_ulid_now() != ulid_util.secure_ulid_now()
