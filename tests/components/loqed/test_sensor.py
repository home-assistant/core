"""Tests the sensors associated with the Loqed integration."""
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_battery(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the battery level sensor entity."""
    entity_id = "sensor.home_battery"

    # Ensure sensor is enabled by default
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is None

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "90"


async def test_battery_voltage(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the battery voltage sensor entity."""
    entity_id = "sensor.home_battery_voltage"

    # Ensure sensor is disabled by default
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable sensor
    entity_registry.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "3.1415"


async def test_battery_type(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the battery type sensor entity."""
    entity_id = "sensor.home_battery_type"

    # Ensure sensor is disabled by default
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable sensor
    entity_registry.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "unknown"


async def test_wifi_strength(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the wifi signal level sensor entity."""
    entity_id = "sensor.home_wi_fi_signal"

    # Ensure sensor is disabled by default
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable sensor
    entity_registry.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "12"


async def test_ble_strength(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the bluetooth signal level sensor entity."""
    entity_id = "sensor.home_bluetooth_signal"

    # Ensure sensor is disabled by default
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Enable sensor
    entity_registry.async_update_entity(entity_id, **{"disabled_by": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "34"
