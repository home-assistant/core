"""Test the RAPT Pill BLE sensors."""

import pytest

from homeassistant.components.rapt_ble.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    COMPLETE_SERVICE_INFO,
    RAPT_MAC,
    V2_NO_VELOCITY_SERVICE_INFO,
    V2_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

VELOCITY_ENTITY_ID = "sensor.rapt_pill_0666_specific_gravity_velocity"


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=RAPT_MAC,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, COMPLETE_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3
    assert hass.states.get(VELOCITY_ENTITY_ID) is None

    temp_sensor = hass.states.get("sensor.rapt_pill_0666_battery")
    assert temp_sensor is not None

    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "43"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "RAPT Pill 0666 Battery"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    temp_sensor = hass.states.get("sensor.rapt_pill_0666_temperature")
    assert temp_sensor is not None

    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "23.81"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "RAPT Pill 0666 Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    temp_sensor = hass.states.get("sensor.rapt_pill_0666_specific_gravity")
    assert temp_sensor is not None

    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "1.0111"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "RAPT Pill 0666 Specific Gravity"
    )
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service_info", "expected_state"),
    [
        pytest.param(V2_SERVICE_INFO, "-14.8217964172363", id="valid_velocity"),
        pytest.param(V2_NO_VELOCITY_SERVICE_INFO, STATE_UNKNOWN, id="invalid_velocity"),
    ],
)
async def test_specific_gravity_velocity_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service_info: BluetoothServiceInfo,
    expected_state: str,
) -> None:
    """Test the specific gravity velocity sensor from a v2 payload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=RAPT_MAC,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    velocity_sensor = hass.states.get(VELOCITY_ENTITY_ID)
    assert velocity_sensor is not None
    assert velocity_sensor.state == expected_state
    assert (
        velocity_sensor.attributes[ATTR_FRIENDLY_NAME]
        == "RAPT Pill 0666 Specific Gravity Velocity"
    )
    assert velocity_sensor.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert velocity_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == "SG points/day"

    entity_entry = entity_registry.async_get(VELOCITY_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.translation_key == "specific_gravity_velocity"
    assert entity_entry.options["sensor"]["suggested_display_precision"] == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
