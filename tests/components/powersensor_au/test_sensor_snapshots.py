"""Snapshot tests for sensor entity state and registry attributes.

These tests set up real config entries, inject library events, and compare
the resulting entity state / registry attributes against syrupy snapshots.
On first run (or after ``pytest --snapshot-update``) the snapshots are
written; subsequent runs assert that nothing has changed unexpectedly.

Run to update snapshots:
    pytest tests/components/powersensor_au/test_sensor_snapshots.py --snapshot-update

Coverage targets:
  - Entity names, unique IDs, device classes, units, state classes
  - State values after representative measurement events
  - Device registry name / identifiers
"""

from collections.abc import Callable, Coroutine
from typing import Any

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.powersensor_au.const import (
    DOMAIN,
    ROLE_HOUSENET,
    ROLE_SOLAR,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"
SOLAR_MAC = "665544332211"


def _entity(hass: HomeAssistant, entry: MockConfigEntry, unique_id: str):
    """Return entity registry entry + state tuple, or fail clearly."""
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
    assert entity_id is not None, f"No entity registered with unique_id={unique_id!r}"
    return reg.async_get(entity_id), hass.states.get(entity_id)


# ---------------------------------------------------------------------------
# Plug snapshot
# ---------------------------------------------------------------------------


async def test_plug_entity_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all plug entities after discovery."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(reg, config_entry.entry_id)
    # Stable sort so snapshot order is deterministic.
    entities.sort(key=lambda e: e.unique_id)
    assert entities == snapshot


# ---------------------------------------------------------------------------
# Sensor snapshot — no role
# ---------------------------------------------------------------------------


async def test_sensor_no_role_entity_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot universal sensor entities before any role is assigned."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(reg, config_entry.entry_id)
    entities.sort(key=lambda e: e.unique_id)
    assert entities == snapshot


# ---------------------------------------------------------------------------
# Sensor snapshot — house-net role with state values
# ---------------------------------------------------------------------------


async def test_sensor_housenet_state_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot entity states for a house-net sensor after representative events."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await fire(
        {
            "event": "battery_level",
            "mac": SENSOR_MAC,
            "volts": 4.15,
        }
    )
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 1500.0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await fire(
        {
            "event": "summation_energy",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "summation_joules": 18_000_000,  # 5 kWh
        }
    )
    await fire(
        {
            "event": "radio_signal_quality",
            "mac": SENSOR_MAC,
            "average_rssi": -72,
        }
    )
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    states = {
        e.unique_id: hass.states.get(e.entity_id)
        for e in sorted(
            er.async_entries_for_config_entry(reg, config_entry.entry_id),
            key=lambda e: e.unique_id,
        )
    }
    assert states == snapshot


# ---------------------------------------------------------------------------
# VHH snapshot — mains + solar
# ---------------------------------------------------------------------------


async def test_vhh_full_state_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot VHH entity states after mains and solar sensors are active."""
    # Mains sensor
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 800.0,
            "starttime_utc": 1700000100,
            "duration_s": 10,
        }
    )

    # Solar sensor
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SOLAR_MAC, "role": ROLE_SOLAR})
    await fire(
        {
            "event": "average_power",
            "mac": SOLAR_MAC,
            "role": ROLE_SOLAR,
            "watts": 300.0,
            "starttime_utc": 1700000100,
            "duration_s": 10,
        }
    )

    await hass.async_block_till_done()

    reg = er.async_get(hass)
    vhh_entries = [
        e
        for e in er.async_entries_for_config_entry(reg, config_entry.entry_id)
        if e.unique_id.startswith(f"{DOMAIN}_vhh_")
    ]
    states = {
        e.unique_id: hass.states.get(e.entity_id)
        for e in sorted(vhh_entries, key=lambda e: e.unique_id)
    }
    assert states == snapshot


# ---------------------------------------------------------------------------
# Device registry snapshot
# ---------------------------------------------------------------------------


async def test_plug_device_registry_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the device registry entry for a discovered plug."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, PLUG_MAC)})
    assert device is not None
    assert device == snapshot


async def test_sensor_device_registry_renames_on_role(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    snapshot: SnapshotAssertion,
) -> None:
    """Device registry entry is updated (translation_key changes) when role is assigned."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    device_before = dev_reg.async_get_device(identifiers={(DOMAIN, SENSOR_MAC)})
    assert device_before is not None
    assert device_before == snapshot(name="before_role")

    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    device_after = dev_reg.async_get_device(identifiers={(DOMAIN, SENSOR_MAC)})
    assert device_after == snapshot(name="after_role")
