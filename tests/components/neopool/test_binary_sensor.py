"""Tests for the NeoPool binary_sensor platform value decoders."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA


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
        "MBF_PAR_HIDRO_COVER_ENABLE": 1,
        "Pool Cover": True,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_OFF

    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_HIDRO_COVER_ENABLE": 1,
        "Pool Cover": False,
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
        "MBF_PAR_HIDRO_COVER_ENABLE": 1,
        "Pool Cover": None,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = _binary_state(hass, mock_config_entry_binary_sensor, "Pool Cover")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "overrides",
    [
        {"MBF_PAR_HIDRO_COVER_ENABLE": 0},
        {"MBF_PAR_HIDRO_COVER_ENABLE": 0x2},
        {},
    ],
)
async def test_pool_cover_unknown_when_detection_disabled(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    overrides: dict[str, int],
) -> None:
    """Cover reads unknown when the cover-enable bit is clear or missing.

    MBF_PAR_HIDRO_COVER_ENABLE packs the cover-detection flag and the
    temperature-shutdown flag in one register. Only the cover-enable bit means
    the controller is tracking the cover; a cleared register (0), the
    temperature-shutdown bit alone (0x2) or a missing register must not surface
    a stale open/closed state.
    """
    await setup_integration(hass, mock_config_entry_binary_sensor)

    data = {
        k: v for k, v in MOCK_POOL_DATA.items() if k != "MBF_PAR_HIDRO_COVER_ENABLE"
    }
    mock_neopool_client.async_read_all.return_value = {
        **data,
        "Pool Cover": False,
        **overrides,
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_opt_in_entities_absent_without_options(
    hass: HomeAssistant,
    mock_config_entry_binary_sensor_no_options: MockConfigEntry,
) -> None:
    """Opt-in entities are not registered when their config option is off.

    Pool Light, the four auxiliary relays, and Pool Cover are gated on an
    integration option in addition to any capability check. With every option
    disabled they must not register, while an ungated relay sensor still does.
    """
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry_binary_sensor_no_options)

    for key in ("Pool Light", "AUX1", "AUX2", "AUX3", "AUX4", "Pool Cover"):
        assert (
            _binary_state(hass, mock_config_entry_binary_sensor_no_options, key) is None
        )
    assert (
        _binary_state(
            hass, mock_config_entry_binary_sensor_no_options, "Filtration Pump"
        )
        is not None
    )
