"""Snapshot tests for inverse platforms."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.inverse.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Specify platforms to test."""
    return [
        Platform.SWITCH,
        Platform.BINARY_SENSOR,
        Platform.LIGHT,
        Platform.FAN,
        Platform.SIREN,
        Platform.COVER,
        Platform.VALVE,
        Platform.LOCK,
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.asyncio
async def test_inverse_platforms_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    platforms: list[Platform],
) -> None:
    """Snapshot all inverse entities for the configured platforms."""

    entries: list[MockConfigEntry] = []
    samples = [
        (Platform.SWITCH, "switch.sample"),
        (Platform.BINARY_SENSOR, "binary_sensor.sample"),
        (Platform.LIGHT, "light.sample"),
        (Platform.FAN, "fan.sample"),
        (Platform.SIREN, "siren.sample"),
        (Platform.COVER, "cover.sample"),
        (Platform.VALVE, "valve.sample"),
        (Platform.LOCK, "lock.sample"),
    ]

    for _, entity_id in samples:
        entry = MockConfigEntry(
            title=f"Inverse {entity_id}",
            domain=DOMAIN,
            data={"entity_id": entity_id},
            entry_id=f"inverse_{entity_id.replace('.', '_')}",
        )
        entry.add_to_hass(hass)
        entries.append(entry)

    await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()

    # Snapshot all platforms together.
    for entry in entries:
        await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
