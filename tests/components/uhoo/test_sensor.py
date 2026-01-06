"""Imports for test_sensor.py."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.uhoo.const import (
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
)
from homeassistant.components.uhoo.sensor import SENSOR_TYPES
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util.dt import utcnow

from . import setup_uhoo_config
from .const import DOMAIN, MOCK_DEVICE

from tests.common import async_fire_time_changed


def assert_expected_properties(
    hass: HomeAssistant, registry: EntityRegistry, serial_number: str, sensor_key: str
) -> None:
    """Assert expected properties for a sensor."""
    # Find the entity description by key
    sensor_desc = None
    for desc in SENSOR_TYPES:
        if desc.key == sensor_key:
            sensor_desc = desc
            break

    assert sensor_desc is not None

    # Build unique ID
    unique_id = f"{serial_number}_{sensor_key}"
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Check attributes
    assert state.attributes.get("device_class") == sensor_desc.device_class
    # Add other assertions as needed


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
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    serial_number = MOCK_DEVICE["serialNumber"]

    unique_id = (
        f"{serial_number}_humidity"  # Adjust based on your actual unique_id format
    )
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    # If that doesn't work, try finding by device and name
    if entity_id is None:
        unique_id = f"{serial_number}_{API_HUMIDITY}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    if entity_id is None:
        all_entities = registry.entities
        for entity_entry in all_entities.values():
            if (
                entity_entry.domain == "sensor"
                and entity_entry.original_name
                and "humidity" in entity_entry.original_name.lower()
            ):
                entity_id = entity_entry.entity_id
                break

    assert entity_id is not None, (
        f"Humidity sensor entity not found. Expected unique_id pattern: {serial_number}_humidity"
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state is not None

    expected_value = "67.6"

    try:
        actual_value = float(state.state)
        assert actual_value == 67.6
    except ValueError:
        assert state.state == expected_value

    with patch(
        "homeassistant.components.uhoo.Client.get_latest_data",
        side_effect=ConnectionError(),
    ):
        future = utcnow() + timedelta(minutes=60)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        # The sensor should keep the last known value
        assert state.state == expected_value

    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == expected_value
