"""Tests for Bravia TV coordinator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


FROZEN_UTC = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

# 09:30+05:00 == 04:30 UTC; frozen at 10:00 UTC → position = 5h30m = 19800 s
PLAYING_INFO = {
    "title": "Test Show",
    "uri": "tv:1",
    "durationSec": 3600,
    "startDateTime": "2024-01-01T09:30:00+05:00",
}


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_playing_info = AsyncMock(return_value=PLAYING_INFO)
    return client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain="braviatv",
        data={
            "pin": "1234",
            "use_psk": False,
            "client_id": "test_client_id",
            "nickname": "BraviaTV",
        },
        title="Bravia TV",
    )
    entry.add_to_hass(hass)
    return entry


async def test_media_position_timezone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """media_position and media_position_updated_at must both be UTC-correct."""
    coordinator = BraviaTVCoordinator(hass, mock_config_entry, mock_client)

    with patch(
        "homeassistant.components.braviatv.coordinator.dt_util.utcnow",
        return_value=FROZEN_UTC,
    ):
        await coordinator.async_update_playing()

    # Proves line 244 fix: cross-timezone position calculation is correct
    assert coordinator.media_position == 19800

    # Proves line 248 fix: updated_at is timezone-aware and in UTC
    assert coordinator.media_position_updated_at is not None
    assert coordinator.media_position_updated_at.tzinfo is not None
    assert coordinator.media_position_updated_at.utcoffset().total_seconds() == 0
