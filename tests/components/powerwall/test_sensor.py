"""Tests for Powerwall sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .mocks import (
    MOCK_GRID_STATUS_DATA,
    MOCK_METERS_DATA,
    MOCK_METERS_DATA_NO_SOLAR,
    create_mock_powerwall_pw3,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_pw3(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test sensor values with Powerwall 3."""
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

    # Check device was created
    reg_device = device_registry.async_get_device(
        identifiers={("powerwall", "192.168.1.100")},
    )
    assert reg_device is not None
    assert reg_device.manufacturer == "Tesla"
    assert reg_device.model == "Powerwall 3"

    # Battery level
    state = hass.states.get("sensor.powerwall_3_battery_level")
    assert state is not None
    assert state.state == "85.5"

    # Battery power
    state = hass.states.get("sensor.powerwall_3_battery_power")
    assert state is not None
    assert state.state == str(round(MOCK_METERS_DATA["battery"]["instant_power"]))

    # Solar power
    state = hass.states.get("sensor.powerwall_3_solar_power")
    assert state is not None
    assert state.state == str(round(MOCK_METERS_DATA["solar"]["instant_power"]))

    # Load power
    state = hass.states.get("sensor.powerwall_3_load_power")
    assert state is not None
    assert state.state == str(round(MOCK_METERS_DATA["load"]["instant_power"]))

    # Grid power
    state = hass.states.get("sensor.powerwall_3_grid_power")
    assert state is not None
    assert state.state == str(round(MOCK_METERS_DATA["site"]["instant_power"]))

    # Grid status
    state = hass.states.get("sensor.powerwall_3_grid_status")
    assert state is not None
    assert state.state == "UP"


async def test_sensors_no_solar(hass: HomeAssistant) -> None:
    """Test sensors when no solar data is available."""
    mock_pw = create_mock_powerwall_pw3()

    # Override poll to return no solar data
    def mock_poll(endpoint: str):
        if endpoint == "/api/meters/aggregates":
            return MOCK_METERS_DATA_NO_SOLAR
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

    # Solar sensor should not exist
    state = hass.states.get("sensor.powerwall_3_solar_power")
    assert state is None

    # But other sensors should still work
    state = hass.states.get("sensor.powerwall_3_battery_level")
    assert state is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensors(hass: HomeAssistant) -> None:
    """Test energy sensor values (Wh to kWh conversion)."""
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

    # Battery energy exported (800000 Wh = 800 kWh)
    state = hass.states.get("sensor.powerwall_3_battery_energy_exported")
    assert state is not None
    assert state.state == "800.0"

    # Battery energy imported (900000 Wh = 900 kWh)
    state = hass.states.get("sensor.powerwall_3_battery_energy_imported")
    assert state is not None
    assert state.state == "900.0"

    # Grid energy imported (500000 Wh = 500 kWh)
    state = hass.states.get("sensor.powerwall_3_grid_energy_imported")
    assert state is not None
    assert state.state == "500.0"

    # Grid energy exported (1000000 Wh = 1000 kWh)
    state = hass.states.get("sensor.powerwall_3_grid_energy_exported")
    assert state is not None
    assert state.state == "1000.0"

    # Solar energy (3000000 Wh = 3000 kWh)
    state = hass.states.get("sensor.powerwall_3_solar_energy")
    assert state is not None
    assert state.state == "3000.0"

    # Load energy (2000000 Wh = 2000 kWh)
    state = hass.states.get("sensor.powerwall_3_load_energy")
    assert state is not None
    assert state.state == "2000.0"
