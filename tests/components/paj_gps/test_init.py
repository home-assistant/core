"""Tests for the PAJ GPS integration setup and coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pajgps_api.models.device import Device
from pajgps_api.pajgps_api_error import (
    AuthenticationError,
    RequestError,
    TokenRefreshError,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)

from homeassistant.components.paj_gps.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(AuthenticationError("Login failed"), id="auth"),
        pytest.param(TokenRefreshError("Refresh failed"), id="token_refresh"),
    ],
)
async def test_auth_error_during_setup_starts_reauth(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test that an auth error on the initial login starts a reauth flow."""
    mock_paj_gps_api.login.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_request_error_during_setup_retries(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a transient error on the initial login retries setup."""
    mock_paj_gps_api.login.side_effect = RequestError("Service unavailable")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


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


@pytest.mark.parametrize(
    "method", ["get_devices", "get_all_last_positions", "get_last_sensor_data"]
)
async def test_request_error_during_update_does_not_start_reauth(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test that a transient request error while polling does not start reauth."""
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

    # pajgps-api raises RequestError when the token refresh or login hits a 5xx
    getattr(mock_paj_gps_api, method).side_effect = RequestError("Service unavailable")
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()
