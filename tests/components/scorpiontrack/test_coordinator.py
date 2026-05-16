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
from homeassistant.exceptions import ConfigEntryError
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
    ("exception", "expected_exception", "message"),
    [
        (
            ScorpionTrackConnectionError("Connection failed"),
            UpdateFailed,
            "Could not reach ScorpionTrack: Connection failed",
        ),
        (
            ScorpionTrackInvalidTokenError("Invalid token"),
            ConfigEntryError,
            "ScorpionTrack rejected the configured share token: Invalid token",
        ),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            ConfigEntryError,
            "Shared location is unavailable: Share expired",
        ),
    ],
)
async def test_async_update_data_maps_client_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    expected_exception: type[Exception],
    message: str,
) -> None:
    """Client errors should be mapped to retryable or setup-failing errors."""
    coordinator = ScorpionTrackCoordinator(
        hass, mock_scorpiontrack_client, mock_config_entry
    )
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    with pytest.raises(expected_exception, match=message):
        await coordinator._async_update_data()
