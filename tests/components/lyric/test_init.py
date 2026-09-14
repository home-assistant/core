"""Tests for the Honeywell Lyric integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiolyric.exceptions import LyricAuthenticationException
from aiolyric.objects.location import LyricLocation
import pytest

from homeassistant.components.lyric.api import OAuth2SessionLyric
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .conftest import build_mock_lyric, location_json, lyric_exception, thermostat_json

from tests.common import MockConfigEntry


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_retry_on_room_priority_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-400 error fetching room priority data should mark the entry as not ready."""
    location = LyricLocation(
        MagicMock(),
        location_json(1, [thermostat_json("AABBCC000001", "LCC-AABBCC000001")]),
    )
    lyric = build_mock_lyric([location])
    lyric.get_thermostat_rooms.side_effect = lyric_exception(500)

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.lyric.Lyric", return_value=lyric):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_retry_on_unexpected_bad_request_reason(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A 400 for a reason other than GetPriorityFailed should mark the entry as not ready."""
    location = LyricLocation(
        MagicMock(),
        location_json(1, [thermostat_json("AABBCC000001", "LCC-AABBCC000001")]),
    )
    lyric = build_mock_lyric([location])
    lyric.get_thermostat_rooms.side_effect = lyric_exception(400, code="SomeOtherError")

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.lyric.Lyric", return_value=lyric):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_error_starts_reauth_on_authentication_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Authentication errors should fail setup and start a reauth flow."""
    location = LyricLocation(
        MagicMock(),
        location_json(1, [thermostat_json("AABBCC000001", "LCC-AABBCC000001")]),
    )
    lyric = build_mock_lyric([location])
    lyric.get_thermostat_rooms.side_effect = LyricAuthenticationException(
        {"request": {}, "response": {}, "status": 401}
    )

    mock_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.lyric.Lyric", return_value=lyric),
        patch.object(OAuth2SessionLyric, "force_refresh_token", new=AsyncMock()),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == SOURCE_REAUTH for flow in flows)
