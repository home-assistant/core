"""Tests for the Actron Air coordinator."""

from unittest.mock import AsyncMock, patch

from actron_neo_api import ActronAirAPIError, ActronAirAuthError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.actron_air.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles auth error during update."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_actron_api.update_status.side_effect = ActronAirAuthError("Auth expired")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # ConfigEntryAuthFailed triggers a reauth flow
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_coordinator_update_api_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles API error during update."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    mock_actron_api.update_status.side_effect = ActronAirAPIError("API error")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # UpdateFailed sets last_update_success to False on the coordinator
    coordinator = list(mock_config_entry.runtime_data.system_coordinators.values())[0]
    assert coordinator.last_update_success is False
