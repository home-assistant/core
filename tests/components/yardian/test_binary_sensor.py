"""Validate Yardian binary sensor behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.yardian.binary_sensor import _zone_enabled_value
from homeassistant.components.yardian.coordinator import YardianZone
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.yardian.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def test_zone_enabled_value_missing_index() -> None:
    """Return None when the zone index is out of range."""
    coordinator = SimpleNamespace(
        data=SimpleNamespace(zones=[YardianZone(name="Zone 1", is_enabled=True)])
    )

    assert _zone_enabled_value(coordinator, 2) is None


async def test_zone_enabled_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """All per-zone binary sensors remain disabled by default."""

    await setup_integration(hass, mock_config_entry)

    for idx in range(1, 3):
        entity_entry = entity_registry.async_get(
            f"binary_sensor.yardian_smart_sprinkler_zone_{idx}_enabled"
        )
        assert entity_entry is not None
        assert entity_entry.disabled
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
