"""Test the ScorpionTrack coordinator."""

from unittest.mock import AsyncMock

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import DOMAIN
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
    ("exception", "expected_exception", "translation_key"),
    [
        (
            ScorpionTrackConnectionError("Connection failed"),
            UpdateFailed,
            "cannot_connect",
        ),
        (
            ScorpionTrackInvalidTokenError("Invalid token"),
            ConfigEntryError,
            "invalid_token",
        ),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            ConfigEntryError,
            "share_unavailable",
        ),
    ],
)
async def test_async_update_data_maps_client_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    expected_exception: type[Exception],
    translation_key: str,
) -> None:
    """Client errors should be mapped to retryable or setup-failing errors."""
    coordinator = ScorpionTrackCoordinator(
        hass, mock_scorpiontrack_client, mock_config_entry
    )
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    with pytest.raises(expected_exception) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
