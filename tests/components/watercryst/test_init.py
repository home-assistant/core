"""Tests for the WATERCryst integration setup."""

from unittest.mock import AsyncMock, patch

from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .conftest import http_status_error, request_error

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api_client")
async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Test standard setup and unloading of the config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WATERCryst",
        unique_id="2026123456789123",
        entry_id="6D9GB5RKL9691HH3RT895JNH56",
        data={CONF_API_KEY: "<api-key>"},
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.ha_device_device_mode") is not None
    assert hass.states.get("sensor.ha_device_event_category") is not None
    assert hass.states.get("sensor.ha_device_event_id") is not None
    assert hass.states.get("sensor.ha_device_last_water_tap_duration") is not None
    assert hass.states.get("sensor.ha_device_last_water_tap_volume") is not None
    assert (
        hass.states.get("sensor.ha_device_microleakage_measurement_state") is not None
    )
    assert (
        hass.states.get("sensor.ha_device_pause_leakage_protection_until") is not None
    )
    assert hass.states.get("sensor.ha_device_pressure") is not None
    assert hass.states.get("sensor.ha_device_today_s_water_consumption") is not None
    assert hass.states.get("sensor.ha_device_total_water_consumption") is not None
    assert hass.states.get("sensor.ha_device_volume_flow_rate") is not None
    assert hass.states.get("sensor.ha_device_water_temperature") is not None

    assert config_entry.runtime_data.biocat_serial_number == "2026123456789123"
    assert config_entry.runtime_data.has_flow_rate_sensor is True
    assert config_entry.runtime_data.has_leakage_protection_system is True
    assert config_entry.runtime_data.has_pressure_sensor is True
    assert config_entry.runtime_data.has_temperature_sensor is True
    assert config_entry.runtime_data.device_info is not None
    assert config_entry.runtime_data.client is not None
    assert config_entry.runtime_data.measurements is not None
    assert config_entry.runtime_data.state is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (WTCApiDisabledError(), ConfigEntryState.SETUP_ERROR),
        (WTCApiTemporaryError(), ConfigEntryState.SETUP_RETRY),
        (WTCApiUnauthorizedError(), ConfigEntryState.SETUP_ERROR),
        (request_error(), ConfigEntryState.SETUP_RETRY),
        (http_status_error(503), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup error and retry handling when API fails."""
    mock_api_client.get_device_info.side_effect = exception

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is state
