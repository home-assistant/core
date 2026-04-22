"""Test the ScorpionTrack coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.coordinator import ScorpionTrackCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_async_update_data_returns_share(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """The coordinator should return the latest share data."""
    coordinator = ScorpionTrackCoordinator(
        hass, mock_scorpiontrack_client, mock_config_entry
    )

    assert await coordinator._async_update_data() is mock_share


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            ScorpionTrackConnectionError("Connection failed"),
            "Could not reach ScorpionTrack: Connection failed",
        ),
        (
            ScorpionTrackInvalidTokenError("Invalid token"),
            "ScorpionTrack rejected the configured share token: Invalid token",
        ),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            "Shared location is unavailable: Share expired",
        ),
    ],
)
async def test_async_update_data_wraps_client_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    message: str,
) -> None:
    """Client errors should be wrapped as update failures."""
    coordinator = ScorpionTrackCoordinator(
        hass, mock_scorpiontrack_client, mock_config_entry
    )
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    with pytest.raises(UpdateFailed, match=message):
        await coordinator._async_update_data()
