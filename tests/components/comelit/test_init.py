"""Tests for Comelit SimpleHome integration init."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "device_identifier_type",
        "old_unique_id_suffix",
        "expected_unique_id_suffix",
        "old_unique_id_removed",
        "config_entry_minor_version",
    ),
    [
        (
            "zone",
            "0",
            "human_status-0",
            True,
            1,
        ),
        (
            "other",
            "0",
            "0",
            False,
            1,
        ),
        (
            "zone",
            "human_status-0",
            "human_status-0",
            False,
            2,
        ),
    ],
)
async def test_migrate_sensor_unique_id(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    device_identifier_type: str,
    old_unique_id_suffix: str,
    expected_unique_id_suffix: str,
    old_unique_id_removed: bool,
    config_entry_minor_version: int,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor unique ID migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_vedo_config_entry.data,
        entry_id=mock_vedo_config_entry.entry_id,
        minor_version=config_entry_minor_version,
    )
    config_entry.add_to_hass(hass)

    old_unique_id = f"{config_entry.entry_id}-{old_unique_id_suffix}"
    new_unique_id = f"{config_entry.entry_id}-{expected_unique_id_suffix}"

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{config_entry.entry_id}-{device_identifier_type}-0")},
    )

    entity_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        old_unique_id,
        config_entry=config_entry,
        device_id=device.id,
    )

    await setup_integration(hass, config_entry)

    migrated_entry = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entry
    assert migrated_entry.unique_id == new_unique_id
    old_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, old_unique_id
    )
    assert (old_entity_id is None) is old_unique_id_removed
    assert (old_entity_id == entity_entry.entity_id) is not old_unique_id_removed

    assert config_entry.version == 1
    assert config_entry.minor_version == 2


async def test_migrate_future_version_returns_false(
    hass: HomeAssistant,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test migration failure for downgraded future config entry version."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_vedo_config_entry.data,
        entry_id=mock_vedo_config_entry.entry_id,
        version=2,
        minor_version=0,
    )

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
