"""Tests for the NeoPool binary_sensor platform value decoders."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform as ep, entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


def _binary_by_key(hass: HomeAssistant, key: str):
    """Return the live binary_sensor entity object for a given _key, or None."""
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("binary_sensor.")
                and getattr(ent, "_key", None) == key
            ):
                return ent
    return None


def _binary_state(hass: HomeAssistant, entity_registry: er.EntityRegistry, key: str):
    """Return the HA state object of the binary_sensor with a given key."""
    entity = _binary_by_key(hass, key)
    if entity is None:
        return None
    return hass.states.get(entity.entity_id)


async def test_direct_key_reflects_coordinator_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer,
) -> None:
    """A simple boolean key from coordinator.data flows straight through is_on."""
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Filtration Pump")
    assert state is not None
    assert state.state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Filtration Pump")
    assert state is not None
    assert state.state == STATE_OFF


async def test_pool_cover_inverts_hardware_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer,
) -> None:
    """Pool Cover: hardware 1 (covered) → HA OFF; hardware 0 → HA ON.

    The OPENING device class needs the opposite polarity from the raw
    register, so the entity inverts the value before returning is_on.
    """
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": True,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Pool Cover")
    assert state is not None
    assert state.state == STATE_OFF

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": False,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Pool Cover")
    assert state is not None
    assert state.state == STATE_ON


async def test_pool_cover_none_yields_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer,
) -> None:
    """Missing Pool Cover key surfaces as STATE_UNKNOWN, not on/off."""
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": None,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Pool Cover")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_pool_cover_unknown_when_filtration_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer,
) -> None:
    """Cover reads unknown while filtration is off, not a false "open"."""
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": False,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = _binary_state(hass, entity_registry, "Pool Cover")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_measurement_module_off_when_filtration_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer,
) -> None:
    """Measurement-module sensors report OFF when the filtration pump is idle."""
    await setup_integration(hass, mock_config_entry_binary_sensor)

    entity = _binary_by_key(hass, "pH measurement active")
    assert entity is not None
    entity_id = entity.entity_id

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "pH measurement active": True,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "pH measurement active": True,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "pH measurement active": True,
        "Filtration Pump": None,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the binary_sensor platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry_binary_sensor)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_binary_sensor.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the binary_sensor entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry_binary_sensor)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_binary_sensor.entry_id
    )
