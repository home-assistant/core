"""Test the Meross Bluetooth sensors."""

import pytest

from homeassistant.components.meross.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ADDRESS,
    CONF_MODEL,
)
from homeassistant.core import HomeAssistant

from . import MEROSS_MS120_ADDRESS, MEROSS_MS120_SERVICE_INFO, MEROSS_MS220_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_ms120_sensors(hass: HomeAssistant) -> None:
    """Test MS120 advertisement creates temperature sensors."""
    inject_bluetooth_service_info(hass, MEROSS_MS120_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        title="Meross MS120",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 6

    temp_sensor = hass.states.get("sensor.meross_ms120_temperature")
    assert temp_sensor is not None
    assert temp_sensor.state == "25.0"
    assert temp_sensor.attributes[ATTR_FRIENDLY_NAME] == "Meross MS120 Temperature"
    assert temp_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor.attributes[ATTR_STATE_CLASS] == "measurement"

    humidity_sensor = hass.states.get("sensor.meross_ms120_humidity")
    assert humidity_sensor is not None
    assert humidity_sensor.state == "50.0"

    battery_sensor = hass.states.get("sensor.meross_ms120_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "80"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_ms220_battery_sensor(hass: HomeAssistant) -> None:
    """Test MS220 only exposes a battery sensor in the first platform set."""
    inject_bluetooth_service_info(hass, MEROSS_MS220_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddee01",
        title="Meross MS220",
        data={
            CONF_ADDRESS: MEROSS_MS220_SERVICE_INFO.address,
            CONF_MODEL: "ms220",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 1
    battery_sensor = hass.states.get("sensor.meross_ms220_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "90"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
