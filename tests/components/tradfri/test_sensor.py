"""Tradfri sensor platform tests."""

from __future__ import annotations

import pytest
from pytradfri.const import (
    ATTR_AIR_PURIFIER_AIR_QUALITY,
    ATTR_DEVICE_BATTERY,
    ATTR_DEVICE_INFO,
    ATTR_REACHABLE_STATE,
    ROOT_AIR_PURIFIER,
)
from pytradfri.device import Device

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.tradfri.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import GATEWAY_ID
from .common import CommandStore, setup_integration

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(scope="module")
def remote_control() -> str:
    """Return a remote control response."""
    return load_fixture("remote_control.json", DOMAIN)


@pytest.mark.parametrize("device", ["remote_control"], indirect=True)
async def test_battery_sensor(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test that a battery sensor is correctly added."""
    entity_id = "sensor.test_battery"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "87"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_DEVICE_INFO: {ATTR_DEVICE_BATTERY: 60}}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "60"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("device", ["blind"], indirect=True)
async def test_cover_battery_sensor(
    hass: HomeAssistant,
    device: Device,
) -> None:
    """Test that a battery sensor is correctly added for a cover (blind)."""
    entity_id = "sensor.test_battery"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "77"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_air_quality_sensor(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test that a battery sensor is correctly added."""
    entity_id = "sensor.test_air_quality"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "5"
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes

    # The sensor returns 65535 if the fan is turned off
    await command_store.trigger_observe_callback(
        hass,
        device,
        {ROOT_AIR_PURIFIER: [{ATTR_AIR_PURIFIER_AIR_QUALITY: 65535}]},
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_filter_time_left_sensor(
    hass: HomeAssistant,
    device: Device,
) -> None:
    """Test that a battery sensor is correctly added."""
    entity_id = "sensor.test_filter_time_left"
    await setup_integration(hass)

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "4320"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.HOURS
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_sensor_available(
    hass: HomeAssistant,
    command_store: CommandStore,
    device: Device,
) -> None:
    """Test sensor available property."""
    entity_id = "sensor.test_filter_time_left"
    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "4320"

    await command_store.trigger_observe_callback(
        hass, device, {ATTR_REACHABLE_STATE: 0}
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device", ["remote_control"], indirect=True)
async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device: Device,
) -> None:
    """Test unique ID is migrated from old format to new."""
    old_unique_id = f"{GATEWAY_ID}-65536"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "gateway_id": GATEWAY_ID,
        },
    )
    entry.add_to_hass(hass)

    # Version 1
    entity_id = "sensor.test"
    entity_name = entity_id.split(".")[1]

    entity_entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        old_unique_id,
        suggested_object_id=entity_name,
        config_entry=entry,
        original_name=entity_name,
    )

    assert entity_entry.entity_id == entity_id
    assert entity_entry.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that new RegistryEntry is using new unique ID format
    new_unique_id = f"{old_unique_id}-battery_level"
    migrated_entity_entry = entity_registry.async_get(entity_id)
    assert migrated_entity_entry is not None
    assert migrated_entity_entry.unique_id == new_unique_id
    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
