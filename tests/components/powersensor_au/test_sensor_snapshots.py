"""Snapshot tests for the Powersensor sensor entities and devices.

Run to update snapshots:
    pytest tests/components/powersensor_au/test_sensor_snapshots.py --snapshot-update
"""

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.powersensor_au.const import (
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_WATER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

PLUG_MAC = "aabbccddeeff"
MAINS_MAC = "112233445566"
SOLAR_MAC = "665544332211"
WATER_MAC = "a1b2c3d4e5f6"
UNASSIGNED_MAC = "0f0e0d0c0b0a"
STARTTIME = 1700000000
RESETTIME = 1690000000

Fire = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


async def _discover_sensor(fire: Fire, mac: str, role: str) -> None:
    """Discover a sensor with the given role, and report its battery and signal."""
    await fire({"event": "device_found", "mac": mac, "device_type": "sensor"})
    await fire(
        {"event": "now_relaying_for", "device_type": "sensor", "mac": mac, "role": role}
    )
    await fire({"event": "battery_level", "mac": mac, "role": role, "volts": 4.15})
    await fire({"event": "radio_signal_quality", "mac": mac, "average_rssi": -72})


async def _discover_installation(hass: HomeAssistant, fire: Fire) -> None:
    """Discover a plug and a sensor of each role, with a reading for each entity."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    for mac, role in (
        (MAINS_MAC, ROLE_HOUSENET),
        (SOLAR_MAC, ROLE_SOLAR),
        (WATER_MAC, ROLE_WATER),
    ):
        await _discover_sensor(fire, mac, role)
    # A sensor that has not reported a role yet.
    await fire(
        {"event": "device_found", "mac": UNASSIGNED_MAC, "device_type": "sensor"}
    )
    await fire({"event": "battery_level", "mac": UNASSIGNED_MAC, "volts": 3.9})
    await fire(
        {"event": "radio_signal_quality", "mac": UNASSIGNED_MAC, "average_rssi": -80}
    )
    # The household view's entities must be listening before it calculates.
    await hass.async_block_till_done()

    await fire(
        {
            "event": "average_power",
            "mac": PLUG_MAC,
            "role": ROLE_APPLIANCE,
            "watts": 120.0,
            "starttime_utc": STARTTIME,
            "duration_s": 1,
        }
    )
    await fire(
        {
            "event": "average_power_components",
            "mac": PLUG_MAC,
            "volts": 240.5,
            "apparent_current": 0.55,
            "active_current": 0.5,
            "reactive_current": 0.23,
            "starttime_utc": STARTTIME,
            "duration_s": 1,
        }
    )
    await fire(
        {
            "event": "summation_energy",
            "mac": PLUG_MAC,
            "summation_joules": 7_200_000,  # 2 kWh
            "starttime_utc": STARTTIME,
            "summation_resettime_utc": RESETTIME,
        }
    )

    # The household view combines solar and mains readings with the same start
    # time, using each only once, so solar has to arrive first.  Its energy
    # comes from the change between two readings.
    for starttime, solar_joules, mains_joules in (
        (STARTTIME, 18_000_000, 18_000_000),
        (STARTTIME + 30, 16_200_000, 18_720_000),
    ):
        for mac, role, watts, joules in (
            (SOLAR_MAC, ROLE_SOLAR, -600.0, solar_joules),
            (MAINS_MAC, ROLE_HOUSENET, 1500.0, mains_joules),
        ):
            await fire(
                {
                    "event": "average_power",
                    "mac": mac,
                    "role": role,
                    "watts": watts,
                    "starttime_utc": starttime,
                    "duration_s": 30,
                }
            )
            await fire(
                {
                    "event": "summation_energy",
                    "mac": mac,
                    "role": role,
                    "summation_joules": joules,
                    "starttime_utc": starttime,
                    "summation_resettime_utc": RESETTIME,
                }
            )

    await fire(
        {
            "event": "average_flow",
            "mac": WATER_MAC,
            "role": ROLE_WATER,
            "litres_per_minute": 9.2,
        }
    )
    await fire(
        {
            "event": "summation_volume",
            "mac": WATER_MAC,
            "role": ROLE_WATER,
            "summation_litres": 132.1,
        }
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Fire,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every entity of an installation, including those disabled by default."""
    await _discover_installation(hass, fire)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Fire,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every device of an installation, household view included."""
    await _discover_installation(hass, fire)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices
    for device in devices:
        assert device == snapshot(name=device.name)


async def test_sensor_device_registry_renames_on_role(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Fire,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Device registry entry is updated (translation_key changes) when role is assigned."""
    await fire({"event": "device_found", "mac": MAINS_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    device_before = device_registry.async_get_device_by_identifier(
        (DOMAIN, MAINS_MAC), config_entry.entry_id
    )
    assert device_before is not None
    assert device_before == snapshot(name="before_role")

    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": MAINS_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()

    device_after = device_registry.async_get_device_by_identifier(
        (DOMAIN, MAINS_MAC), config_entry.entry_id
    )
    assert device_after == snapshot(name="after_role")
