"""Test Traccar Server diagnostics."""

from collections.abc import Generator
from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )
    # Sort the list of entities
    result["entities"] = sorted(
        result["entities"], key=lambda entity: entity["entity_id"]
    )

    assert result == snapshot(name="entry")


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device diagnostics."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry,
        mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    for device in dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ):
        entities = er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        )
        # Enable all entities to show everything in snapshots
        for entity in entities:
            entity_registry.async_update_entity(entity.entity_id, disabled_by=None)

        result = await get_diagnostics_for_device(
            hass, hass_client, mock_config_entry, device=device
        )
        # Sort the list of entities
        result["entities"] = sorted(
            result["entities"], key=lambda entity: entity["entity_id"]
        )

        assert result == snapshot(name=device.name)


async def test_device_diagnostics_with_disabled_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_traccar_api_client: Generator[AsyncMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device diagnostics with disabled entity."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        device_registry,
        mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    for device in dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ):
        for entry in er.async_entries_for_device(
            entity_registry,
            device.id,
            include_disabled_entities=True,
        ):
            entity_registry.async_update_entity(
                entry.entity_id,
                disabled_by=er.RegistryEntryDisabler.USER,
            )

        result = await get_diagnostics_for_device(
            hass, hass_client, mock_config_entry, device=device
        )
        # Sort the list of entities
        result["entities"] = sorted(
            result["entities"], key=lambda entity: entity["entity_id"]
        )

        assert result == snapshot(name=device.name)
