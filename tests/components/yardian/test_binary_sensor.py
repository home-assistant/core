"""Validate Yardian binary sensor behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.yardian.binary_sensor import _zone_enabled_value
from homeassistant.components.yardian.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Validate created binary sensors without relying on snapshots."""
    with patch("homeassistant.components.yardian.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_ids = {entry.entity_id for entry in entries}
    assert entity_ids == {
        "binary_sensor.yardian_smart_sprinkler_watering_running",
        "binary_sensor.yardian_smart_sprinkler_standby",
        "binary_sensor.yardian_smart_sprinkler_freeze_prevent",
        "binary_sensor.yardian_smart_sprinkler_zone_1_enabled",
        "binary_sensor.yardian_smart_sprinkler_zone_2_enabled",
    }

    states = {state.entity_id: state.state for state in hass.states.async_all()}
    assert states["binary_sensor.yardian_smart_sprinkler_watering_running"] == "on"
    assert states["binary_sensor.yardian_smart_sprinkler_standby"] == "on"
    assert states["binary_sensor.yardian_smart_sprinkler_freeze_prevent"] == "on"
    assert states["binary_sensor.yardian_smart_sprinkler_zone_1_enabled"] == "on"
    assert states["binary_sensor.yardian_smart_sprinkler_zone_2_enabled"] == "off"


async def test_zone_enabled_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """All per-zone binary sensors remain disabled by default."""

    await setup_integration(hass, mock_config_entry)

    for idx in range(2):
        entity_id = entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{mock_config_entry.unique_id}-zone_enabled_{idx}"
        )
        assert entity_id is not None
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.disabled
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


def test_zone_enabled_value_handles_index_error() -> None:
    """Out-of-range zones return None without raising."""

    coordinator = SimpleNamespace(
        data=SimpleNamespace(zones=[["Zone 1", 1], ["Zone 2", 0]])
    )
    assert _zone_enabled_value(coordinator, 5) is None


def test_zone_enabled_value_handles_type_error() -> None:
    """Non-subscriptable zone data returns None."""

    coordinator = SimpleNamespace(data=SimpleNamespace(zones=None))
    assert _zone_enabled_value(coordinator, 0) is None
