"""Test Home Assistant uuid util methods."""

from unittest.mock import patch
import uuid

from homeassistant.util import uuid as uuid_util


async def test_uuid_util_random_uuid_hex() -> None:
    """Verify we can generate a random uuid."""
    assert len(uuid_util.random_uuid_hex()) == 32
    assert uuid.UUID(uuid_util.random_uuid_hex())


async def test_secure_uuid_hex() -> None:
    """Verify a secure uuid hex comes from secrets."""
    with patch(
        "homeassistant.util.uuid.secrets.token_hex", return_value="ab" * 16
    ) as mock_token_hex:
        assert uuid_util.secure_uuid_hex() == "ab" * 16

    mock_token_hex.assert_called_once_with(16)
    assert len(uuid_util.secure_uuid_hex()) == 32
    assert uuid.UUID(uuid_util.secure_uuid_hex())
