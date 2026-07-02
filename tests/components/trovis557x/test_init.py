"""Tests for the Trovis 557x config-entry setup."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DOMAIN

from tests.common import MockConfigEntry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_creates_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads and produces entities across every platform."""
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    outside = hass.states.get("sensor.trovis_5579_outside_temperature")
    assert outside is not None
    assert outside.state == "12.3"

    pump = hass.states.get("binary_sensor.heating_circuit_1_pump")
    assert pump is not None
    assert pump.state == "on"

    climate = hass.states.get("climate.heating_circuit_1")
    assert climate is not None
    assert climate.state == "auto"  # mode AUTOMATIC
    assert climate.attributes["temperature"] == 21.0  # room_setpoint_active
    assert climate.attributes["current_temperature"] == 20.0  # room_temperature

    water = hass.states.get("water_heater.hot_water")
    assert water is not None
    assert water.attributes["temperature"] == 50.0  # setpoint_active
    assert water.attributes["current_temperature"] == 45.0  # storage_temperature


async def test_sub_devices_via_controller(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Each circuit / hot water is a sub-device linked via the controller."""
    await _setup(hass, mock_config_entry)
    registry = dr.async_get(hass)

    controller = registry.async_get_device({(DOMAIN, mock_config_entry.entry_id)})
    assert controller is not None

    circuit_1 = registry.async_get_device(
        {(DOMAIN, f"{mock_config_entry.entry_id}_circuit_1")}
    )
    assert circuit_1 is not None
    assert circuit_1.via_device_id == controller.id
    assert circuit_1.name == "Heating circuit 1"

    hot_water = registry.async_get_device(
        {(DOMAIN, f"{mock_config_entry.entry_id}_hot_water")}
    )
    assert hot_water is not None
    assert hot_water.via_device_id == controller.id


async def test_climate_set_hvac_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting HVAC mode writes through and takes effect on the next read."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.heating_circuit_1", "hvac_mode": "heat"},
        blocking=True,
    )
    await hass.async_block_till_done()

    climate = hass.states.get("climate.heating_circuit_1")
    assert climate is not None
    assert climate.state == "heat"
