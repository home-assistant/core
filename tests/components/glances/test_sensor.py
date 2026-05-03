"""Tests for Glances sensors."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.glances.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HA_SENSOR_DATA, MOCK_REFERENCE_DATE, MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states are correctly collected from library."""

    freezer.move_to(MOCK_REFERENCE_DATE)

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


async def test_uptime_variation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_api: AsyncMock
) -> None:
    """Test uptime small variation update."""

    # Init with reference time
    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    uptime_state = hass.states.get("sensor.0_0_0_0_uptime").state

    # Time change should not change uptime (absolute date)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    uptime_state2 = hass.states.get("sensor.0_0_0_0_uptime").state
    assert uptime_state2 == uptime_state

    mock_data = HA_SENSOR_DATA.copy()
    mock_data["uptime"] = "1:25:20"
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    # Server has been restarted so therefore we should have a new state
    freezer.move_to(MOCK_REFERENCE_DATE + timedelta(days=2))
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.0_0_0_0_uptime").state == "2024-02-15T12:49:52+00:00"


async def test_sensor_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor removed server side."""

    # Init with reference time
    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.0_0_0_0_ssl_disk_used").state != STATE_UNAVAILABLE
    assert hass.states.get("sensor.0_0_0_0_memory_use").state != STATE_UNAVAILABLE
    assert hass.states.get("sensor.0_0_0_0_uptime").state != STATE_UNAVAILABLE

    # Remove some sensors from Glances API data
    mock_data = HA_SENSOR_DATA.copy()
    mock_data.pop("fs")
    mock_data.pop("mem")
    mock_data.pop("uptime")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    # Server stops providing some sensors, so state should switch to Unavailable
    freezer.move_to(MOCK_REFERENCE_DATE + timedelta(minutes=2))
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.0_0_0_0_ssl_disk_used").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.0_0_0_0_memory_use").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.0_0_0_0_uptime").state == STATE_UNAVAILABLE


async def test_dynamic_sensor_auto_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Dynamic entities are removed from the registry when their device disappears."""

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-tx")
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-lo-rx")

    # eth0 disappears (e.g. a Docker bridge network is removed) but the
    # `network` block itself is still populated.
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data["network"].pop("eth0")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx") is None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-tx") is None
    # Other interfaces remain registered.
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-lo-rx")


async def test_dynamic_sensor_auto_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Dynamic entities are added when a new device appears in the API response."""

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth1-rx") is None

    # A new interface appears (e.g. a Docker bridge network is created).
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data["network"]["eth1"] = {
        "is_up": True,
        "rx": 1234,
        "tx": 5678,
        "speed": 1000.0,
    }
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth1-rx")
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth1-tx")
    eth1_rx_state = hass.states.get("sensor.0_0_0_0_eth1_rx")
    assert eth1_rx_state is not None
    assert eth1_rx_state.state != STATE_UNAVAILABLE
