"""Imports for test_sensor.py."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.components.uhooair.const import (
    API_CO,
    API_CO2,
    API_HUMIDITY,
    API_MOLD,
    API_NO2,
    API_OZONE,
    API_PM25,
    API_PRESSURE,
    API_TEMP,
    API_TVOC,
    API_VIRUS,
    ATTR_LABEL,
    SENSOR_TYPES,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util.dt import utcnow

from . import setup_uhoo_config
from .const import MOCK_DEVICE, MOCK_DEVICE_DATA

from tests.common import async_fire_time_changed


def assert_expected_properties(
    hass: HomeAssistant,
    registry: EntityRegistry,
    serial_number: str,
    sensor_type: str,
) -> None:
    """Assert expected properties."""

    device_name = str(MOCK_DEVICE["deviceName"]).lower().replace(" ", "_")
    sensor_name = (
        str(SENSOR_TYPES[sensor_type][ATTR_LABEL])
        .lower()
        .replace(" ", "_")
        .replace(".", "_")
    )

    state = hass.states.get(f"sensor.{device_name}_{sensor_name}")
    CAMEL_MAP = {
        "air_pressure": "airPressure",
        "virus_index": "virusIndex",
        "mold_index": "moldIndex",
    }
    assert state
    if sensor_type in ["air_pressure", "virus_index", "mold_index"]:
        assert state.state == f"{float(MOCK_DEVICE_DATA[0][CAMEL_MAP[sensor_type]])!s}"
    else:
        assert state.state == f"{float(MOCK_DEVICE_DATA[0][sensor_type])!s}"

    # Attributes
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS)
        == SENSOR_TYPES[sensor_type][ATTR_DEVICE_CLASS]
    )
    assert state.attributes.get(ATTR_ICON) == SENSOR_TYPES[sensor_type][ATTR_ICON]
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SENSOR_TYPES[sensor_type][ATTR_UNIT_OF_MEASUREMENT]
    )

    assert (
        state.attributes.get(ATTR_DEVICE_CLASS)
        == SENSOR_TYPES[sensor_type][ATTR_DEVICE_CLASS]
    )

    entity = registry.async_get(f"sensor.{device_name}_{sensor_name}")

    assert entity
    assert entity.unique_id == f"{serial_number}_{sensor_type}"


async def test_sensors(
    hass: HomeAssistant,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test states of the sensors."""

    serial_number = MOCK_DEVICE["serialNumber"]

    await setup_uhoo_config(hass)
    registry: EntityRegistry = er.async_get(hass)

    assert_expected_properties(hass, registry, serial_number, API_CO)
    assert_expected_properties(hass, registry, serial_number, API_CO2)
    assert_expected_properties(hass, registry, serial_number, API_PM25)
    assert_expected_properties(hass, registry, serial_number, API_HUMIDITY)
    assert_expected_properties(hass, registry, serial_number, API_TEMP)
    assert_expected_properties(hass, registry, serial_number, API_PRESSURE)
    assert_expected_properties(hass, registry, serial_number, API_TVOC)
    assert_expected_properties(hass, registry, serial_number, API_NO2)
    assert_expected_properties(hass, registry, serial_number, API_OZONE)
    assert_expected_properties(hass, registry, serial_number, API_VIRUS)
    assert_expected_properties(hass, registry, serial_number, API_MOLD)


async def test_availability(
    hass: HomeAssistant,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test availability of data."""
    await setup_uhoo_config(hass)

    state = hass.states.get("sensor.office_room_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "67.6"

    with patch(
        "homeassistant.components.uhooair.Client.get_latest_data",
        side_effect=ConnectionError(),
    ):
        future = utcnow() + timedelta(minutes=60)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.office_room_humidity")
        assert state
        assert state.state == "67.6"

    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.office_room_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "67.6"
