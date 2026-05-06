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


async def test_dynamic_sensor_recreated_after_removal(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A dynamic sensor reappears in the registry if its device comes back."""

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")

    # eth0 disappears.
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data["network"].pop("eth0")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx") is None

    # eth0 comes back on a later update.
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=HA_SENSOR_DATA)

    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-tx")


async def test_orphan_entities_cleaned_at_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Stale registry entries from removed devices are cleaned up at setup."""

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    # Pre-register orphans for devices that no longer appear in the API data:
    # a removed Docker bridge network and a removed mount point.
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="test-veth1234abc-rx",
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="test-veth1234abc-tx",
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="test-/old/mount-disk_use",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Orphans are gone.
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "test-veth1234abc-rx")
        is None
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "test-veth1234abc-tx")
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "test-/old/mount-disk_use"
        )
        is None
    )
    # Live entities are still registered.
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-/ssl-disk_use")


async def test_label_with_description_key_suffix_is_kept(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A live mount whose label ends with a description key suffix is preserved.

    Regression guard: the cleanup must identify entities by membership in the
    expected unique_id set, not by parsing labels out of unique_ids.
    """

    freezer.move_to(MOCK_REFERENCE_DATE)
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    # Mountpoint whose name happens to end with a description key.
    mock_data["fs"]["/var/lib/disk_use"] = {
        "disk_use": 1.0,
        "disk_use_percent": 1.0,
        "disk_free": 1.0,
        "disk_size": 2.0,
    }
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test-/var/lib/disk_use-disk_use"
    )
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test-/var/lib/disk_use-disk_use_percent"
    )

    # Another fs disappears; the colliding-named mount must stay.
    mock_data2 = copy.deepcopy(mock_data)
    mock_data2["fs"].pop("/media")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data2)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "test-/media-disk_use")
        is None
    )
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "test-/var/lib/disk_use-disk_use"
    )


async def test_fan_speed_no_cross_type_removal(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A gpu fan_speed entity must not be removed when the sensors plugin is empty.

    The `fan_speed` description key is shared between the `gpu` and `sensors`
    types. Removal must only fire when every owning type has a non-empty
    parent in the current refresh.
    """

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    gpu_fan_unique_id = "test-NVIDIA GeForce RTX 3080 (GPU 0)-fan_speed"
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, gpu_fan_unique_id)

    # `sensors` plugin goes empty (transient gap on that plugin only).
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data["sensors"] = {}
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, gpu_fan_unique_id)


async def test_transient_missing_parent_keeps_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A missing parent type is treated as a transient gap, not authoritative removal.

    Mirrors what `glances_api` produces when a plugin's upstream data is
    empty or unavailable: the type key is absent from the returned dict
    rather than mapping to an empty dict.
    """

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")

    # network plugin drops out entirely — entities must remain registered.
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data.pop("network")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert hass.states.get("sensor.0_0_0_0_eth0_rx").state == STATE_UNAVAILABLE

    # network reappears with the same interface — entity becomes available again.
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=HA_SENSOR_DATA)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert hass.states.get("sensor.0_0_0_0_eth0_rx").state != STATE_UNAVAILABLE


async def test_disabled_entity_preference_preserved(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """User-disabled entities are not auto-removed when their device disappears."""

    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    eth0_rx = entity_registry.async_get_entity_id("sensor", DOMAIN, "test-eth0-rx")
    assert eth0_rx
    entity_registry.async_update_entity(
        eth0_rx, disabled_by=er.RegistryEntryDisabler.USER
    )

    # eth0 disappears.
    mock_data = copy.deepcopy(HA_SENSOR_DATA)
    mock_data["network"].pop("eth0")
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    reg_entry = entity_registry.async_get(eth0_rx)
    assert reg_entry is not None
    assert reg_entry.disabled_by is er.RegistryEntryDisabler.USER
