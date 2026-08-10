"""Tests for the NeoPool button platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from neopool_modbus.exceptions import NeoPoolConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


def _button_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key_lower: str
) -> str:
    """Resolve a button entity by its trailing unique_id segment."""
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == BUTTON_DOMAIN and e.unique_id.endswith(f"_{key_lower}")
    ]
    assert entries, f"no button entity ending in _{key_lower}"
    return entries[0].entity_id


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {"entity_id": entity_id},
        blocking=True,
    )


async def test_sync_time_button_writes_time_and_commit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """SYNC_TIME button delegates to async_sync_device_time."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _button_entity_id(hass, mock_config_entry, "sync_time")
    mock_neopool_client.async_sync_device_time.reset_mock()
    await _press(hass, entity_id)
    assert mock_neopool_client.async_sync_device_time.await_count == 1


async def test_escape_button_writes_clear_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """MBF_ESCAPE button delegates to async_clear_errors."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _button_entity_id(hass, mock_config_entry, "mbf_escape")
    mock_neopool_client.async_clear_errors.reset_mock()
    await _press(hass, entity_id)
    mock_neopool_client.async_clear_errors.assert_awaited_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reset_cell_partial_button_writes_reset_and_save(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """RESET_CELL_PARTIAL delegates to async_reset_user_counters."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _button_entity_id(hass, mock_config_entry, "reset_cell_partial")
    mock_neopool_client.async_reset_user_counters.reset_mock()
    await _press(hass, entity_id)
    mock_neopool_client.async_reset_user_counters.assert_awaited_once()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_reset_cell_partial_button_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reset button registers but is disabled-by-default (destructive action)."""
    await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    matches = [
        e
        for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
        if e.domain == BUTTON_DOMAIN and e.unique_id.endswith("_reset_cell_partial")
    ]
    assert len(matches) == 1
    assert matches[0].disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_reset_cell_partial_button_skipped_without_hydrolysis(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """No RESET_CELL_PARTIAL entity is registered when hydrolysis isn't detected."""
    no_hidro_data = dict(mock_neopool_client.async_read_all.return_value)
    no_hidro_data["Hydrolysis module detected"] = False
    mock_neopool_client.async_read_all.return_value = no_hidro_data

    await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    matches = [
        e
        for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
        if e.domain == BUTTON_DOMAIN and e.unique_id.endswith("_reset_cell_partial")
    ]
    assert matches == []


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_button_press_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    write_error: Exception,
) -> None:
    """Communication errors on button press are surfaced as translated HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _button_entity_id(hass, mock_config_entry, "sync_time")

    mock_neopool_client.async_sync_device_time.side_effect = write_error
    with pytest.raises(HomeAssistantError):
        await _press(hass, entity_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the button platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the button entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
