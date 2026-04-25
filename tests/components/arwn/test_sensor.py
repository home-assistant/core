"""Tests for arwn sensor platform."""

import pytest

from homeassistant.components.arwn.const import DOMAIN
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ambient Radio Weather Network",
        entry_id="TEST_ENTRY_ID",
    )
    entry.add_to_hass(hass)
    return entry


async def test_temperature_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test temperature sensor is created on first MQTT message."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/temperature/BackYard",
        '{"temp": 72.5, "units": "F"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "arwn/temperature/BackYard"
    )
    assert entity is not None

    state = hass.states.get(entity)
    assert state is not None
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["unit_of_measurement"] in (
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.CELSIUS,
    )


async def test_temperature_sensor_state_update(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test that a second MQTT message updates state, not adds a new entity."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "arwn/temperature/BackYard", '{"temp": 72.5, "units": "F"}'
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "arwn/temperature/BackYard"
    )
    state_after_first = hass.states.get(entity_id).state
    assert state_after_first not in ("unknown", "unavailable")

    async_fire_mqtt_message(
        hass, "arwn/temperature/BackYard", '{"temp": 75.0, "units": "F"}'
    )
    await hass.async_block_till_done()

    state_after_second = hass.states.get(entity_id).state
    assert state_after_second not in ("unknown", "unavailable")
    assert state_after_second != state_after_first

    # Only one entity should exist for this config entry
    entries = [
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
    ]
    assert len(entries) == 1


async def test_wind_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test wind message creates speed, gust, and direction sensors."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/wind",
        '{"speed": 12.3, "gust": 18.0, "direction": 270, "units": "mph"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
    }
    assert "arwn/wind/speed" in unique_ids
    assert "arwn/wind/gust" in unique_ids
    assert "arwn/wind/dir" in unique_ids


async def test_rain_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test rain message creates total and rate sensors."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/rain",
        '{"total": 1.2, "rate": 0.1, "units": "in"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
    }
    assert "arwn/rain/total" in unique_ids
    assert "arwn/rain/rate" in unique_ids


async def test_rain_today_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test arwn/rain/today creates since_midnight sensor."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/rain/today",
        '{"since_midnight": 0.5, "units": "in"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
    }
    assert "arwn/rain/today" in unique_ids


async def test_barometer_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test barometer sensor is created."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/barometer",
        '{"pressure": 1013.25, "units": "mb"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "arwn/barometer"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state not in ("unknown", "unavailable")


async def test_moisture_sensor_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test moisture sensor is created."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/moisture/FrontLawn",
        '{"moisture": 45.2, "units": "%"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "arwn/moisture/FrontLawn"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state not in ("unknown", "unavailable")


async def test_unknown_domain_ignored(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test that messages on unknown sub-topics create no entities."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/unknown_sensor",
        '{"value": 1.0}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = [
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
    ]
    assert len(entries) == 0


async def test_entry_unload_removes_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    config_entry: MockConfigEntry,
) -> None:
    """Test that unloading the config entry marks all sensors unavailable."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/temperature/BackYard",
        '{"temp": 72.5, "units": "F"}',
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "arwn/temperature/BackYard"
    )
    assert entity_id is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
