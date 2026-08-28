"""Tests for the NeoPool binary_sensor platform value decoders."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.decoders import encode_device_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


def _binary_state(hass: HomeAssistant, entry: MockConfigEntry, key: str):
    """Return the HA state object of the binary_sensor for a coordinator key."""
    registry = er.async_get(hass)
    suffix = f"_{key.lower()}"
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == BINARY_SENSOR_DOMAIN and e.unique_id.endswith(suffix)
    ]
    if not entries:
        return None
    return hass.states.get(entries[0].entity_id)


async def test_direct_key_reflects_coordinator_value(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A simple boolean key from coordinator.data flows straight through is_on."""
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Filtration Pump")
    assert state is not None
    assert state.state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Filtration Pump")
    assert state is not None
    assert state.state == STATE_OFF


async def test_pool_cover_inverts_hardware_value(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
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
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_OFF

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": False,
        "Filtration Pump": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_ON


async def test_pool_cover_none_yields_unknown(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
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
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("pump_state", [False, None])
async def test_pool_cover_unknown_when_filtration_not_running(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    pump_state: bool | None,
) -> None:
    """Cover reads unknown unless the pump is confirmed running.

    The device only reports the cover bit while filtration runs, so an idle
    (False) or unknown (None) pump state must not surface a stale open/closed.
    """
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Pool Cover": False,
        "Filtration Pump": pump_state,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_measurement_module_reads_raw_bit(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Measurement-module sensors report the raw device bit, even with filtration off.

    The controller keeps measuring the probes regardless of the filtration
    pump state, so the entity must not force the value off.
    """
    await setup_integration(hass, mock_config_entry_binary_sensor)

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "pH measurement active": True,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(
        hass, mock_config_entry_binary_sensor, "pH measurement active"
    )
    assert state is not None
    assert state.state == STATE_ON

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "pH measurement active": False,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(
        hass, mock_config_entry_binary_sensor, "pH measurement active"
    )
    assert state is not None
    assert state.state == STATE_OFF


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("time_zone", ["UTC", "America/New_York"])
async def test_device_time_drift(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
) -> None:
    """The drift sensor decodes MBF_PAR_TIME in the HA timezone and thresholds it.

    MBF_PAR_TIME is the device wall-clock encoded as naive epoch seconds. In
    sync means the decoded clock matches HA now within a minute; a two-minute
    offset trips the PROBLEM sensor. Both the UTC and a non-UTC timezone are
    exercised so the tz normalisation is covered.
    """
    await hass.config.async_set_time_zone(time_zone)
    freezer.move_to("2024-01-02 08:04:05+00:00")
    tz = dt_util.get_time_zone(time_zone)
    await setup_integration(hass, mock_config_entry_binary_sensor)

    # Device clock matches HA wall-clock after the poll tick: OFF.
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_TIME": encode_device_time(dt_util.now(tz) + timedelta(seconds=60)),
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(
        hass, mock_config_entry_binary_sensor, "Device Time Out Of Sync"
    )
    assert state is not None
    assert state.state == STATE_OFF

    # Device clock two minutes ahead of HA: over the 60 s threshold, so ON.
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_TIME": encode_device_time(
            dt_util.now(tz) + timedelta(seconds=60) + timedelta(minutes=2)
        ),
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(
        hass, mock_config_entry_binary_sensor, "Device Time Out Of Sync"
    )
    assert state is not None
    assert state.state == STATE_ON
