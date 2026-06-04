"""Tests for the Cielo Home sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.cielo_home.const import (
    DOMAIN,
    SENSOR_HUMIDITY,
    SENSOR_TEMPERATURE,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry


async def test_sensor_entities_created(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that temperature and humidity sensor entities are created."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    sensor_entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == DOMAIN and e.domain == "sensor"
    ]
    assert len(sensor_entities) == 2


async def test_temperature_sensor_state(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cielo_device_api: MagicMock,
) -> None:
    """Test temperature sensor reports correct state and attributes."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_living_room_temperature")
    assert state is not None
    assert state.state == "22"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE


async def test_humidity_sensor_state(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cielo_device_api: MagicMock,
) -> None:
    """Test humidity sensor reports correct state and attributes."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_living_room_humidity")
    assert state is not None
    assert state.state == "40"
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE
    assert state.attributes.get("device_class") == SensorDeviceClass.HUMIDITY


async def test_temperature_sensor_unique_id(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test temperature sensor has the expected unique ID."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get("sensor.living_room_living_room_temperature")
    assert entry is not None
    assert entry.unique_id == f"device_1-{SENSOR_TEMPERATURE}"


async def test_humidity_sensor_unique_id(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test humidity sensor has the expected unique ID."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get("sensor.living_room_living_room_humidity")
    assert entry is not None
    assert entry.unique_id == f"device_1-{SENSOR_HUMIDITY}"


async def test_temperature_sensor_fahrenheit_unit(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cielo_device_api: MagicMock,
) -> None:
    """Test temperature sensor reports Fahrenheit when device is configured for it."""
    mock_cielo_device_api.temperature_unit.return_value = "°F"

    hass.config.units = US_CUSTOMARY_SYSTEM

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_living_room_temperature")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT
