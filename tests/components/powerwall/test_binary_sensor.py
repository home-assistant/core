"""Tests for Powerwall binary sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .mocks import MOCK_GRID_STATUS_DATA, MOCK_METERS_DATA, create_mock_powerwall_pw3

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_pw3(hass: HomeAssistant) -> None:
    """Test binary sensor values with Powerwall 3."""
    mock_pw = create_mock_powerwall_pw3()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Grid connected (grid_status == "UP")
    state = hass.states.get("binary_sensor.powerwall_3_grid_connected")
    assert state is not None
    assert state.state == STATE_ON

    # Battery charging (battery power < 0 means charging)
    # Mock data has battery.instant_power = -1500 (charging)
    state = hass.states.get("binary_sensor.powerwall_3_battery_charging")
    assert state is not None
    assert state.state == STATE_ON

    # Grid services active
    state = hass.states.get("binary_sensor.powerwall_3_grid_services_active")
    assert state is not None
    assert state.state == STATE_OFF  # Mock data has grid_services_active = False


async def test_binary_sensors_grid_down(hass: HomeAssistant) -> None:
    """Test binary sensors when grid is down."""
    mock_pw = create_mock_powerwall_pw3()

    # Override poll to return grid down status
    def mock_poll(endpoint: str):
        if endpoint == "/api/meters/aggregates":
            return MOCK_METERS_DATA
        if endpoint == "/api/system_status/grid_status":
            return {
                "grid_status": "SystemIslandedActive",
                "grid_services_active": False,
            }
        return None

    mock_pw.poll.side_effect = mock_poll
    mock_pw.grid_status.return_value = "DOWN"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Grid connected should be OFF when grid is down
    state = hass.states.get("binary_sensor.powerwall_3_grid_connected")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensors_battery_discharging(hass: HomeAssistant) -> None:
    """Test battery charging sensor when discharging."""
    mock_pw = create_mock_powerwall_pw3()

    # Override poll to return positive battery power (discharging)
    meters_discharging = dict(MOCK_METERS_DATA)
    meters_discharging["battery"] = dict(MOCK_METERS_DATA["battery"])
    meters_discharging["battery"]["instant_power"] = 1500  # Positive = discharging

    def mock_poll(endpoint: str):
        if endpoint == "/api/meters/aggregates":
            return meters_discharging
        if endpoint == "/api/system_status/grid_status":
            return MOCK_GRID_STATUS_DATA
        return None

    mock_pw.poll.side_effect = mock_poll

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Battery charging should be OFF when discharging
    state = hass.states.get("binary_sensor.powerwall_3_battery_charging")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensors_grid_services_active(hass: HomeAssistant) -> None:
    """Test grid services active sensor."""
    mock_pw = create_mock_powerwall_pw3()

    # Override poll to return grid services active
    def mock_poll(endpoint: str):
        if endpoint == "/api/meters/aggregates":
            return MOCK_METERS_DATA
        if endpoint == "/api/system_status/grid_status":
            return {
                "grid_status": "SystemGridConnected",
                "grid_services_active": True,
            }
        return None

    mock_pw.poll.side_effect = mock_poll

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "test123",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Grid services active should be ON
    state = hass.states.get("binary_sensor.powerwall_3_grid_services_active")
    assert state is not None
    assert state.state == STATE_ON
