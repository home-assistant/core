"""Tests for the PAJ GPS integration setup and coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pajgps_api.models.device import Device
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import pytest

from homeassistant.components.paj_gps.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)


@pytest.mark.parametrize(
    ("method", "exception"),
    [
        pytest.param("get_devices", AuthenticationError("Unauthorized"), id="devices"),
        pytest.param(
            "get_all_last_positions",
            AuthenticationError("Unauthorized"),
            id="positions",
        ),
        pytest.param(
            "get_last_sensor_data", AuthenticationError("Unauthorized"), id="voltage"
        ),
        pytest.param(
            "get_devices", TokenRefreshError("Refresh failed"), id="token_refresh"
        ),
    ],
)
async def test_auth_error_during_update_starts_reauth(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
    exception: Exception,
) -> None:
    """Test that an auth error while polling starts a reauth flow."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            **{
                **await async_load_json_object_fixture(hass, "device.json", DOMAIN),
                "device_models": [{"alarm_volt": 1}],
            }
        )
    ]
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    getattr(mock_paj_gps_api, method).side_effect = exception
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
