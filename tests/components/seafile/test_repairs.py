"""Test the Seafile repairs."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.seafile.const import DOMAIN
from homeassistant.components.seafile.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import LIBRARY_ID, SUBENTRY_ID

ISSUE_ID = f"library_deleted_{SUBENTRY_ID}"


@pytest.fixture
def mock_library_deleted(mock_seafile_client: AsyncMock) -> AsyncMock:
    """Remove the configured library from the libraries on the server."""
    mock_seafile_client.get_libraries.return_value = [
        library
        for library in mock_seafile_client.get_libraries.return_value
        if library.id != LIBRARY_ID
    ]
    return mock_seafile_client


async def test_issue_follows_library(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue is created when the library is deleted and removed when it is back."""
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None

    libraries = mock_seafile_client.get_libraries.return_value
    mock_seafile_client.get_libraries.return_value = [
        library for library in libraries if library.id != LIBRARY_ID
    ]
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "library_deleted"
    assert issue.translation_placeholders == {"name": "Documents"}
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is True
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.data == {
        "entry_id": mock_config_entry.entry_id,
        "subentry_id": SUBENTRY_ID,
        "name": "Documents",
    }
    assert hass.states.get("sensor.documents_size").state == STATE_UNAVAILABLE

    mock_seafile_client.get_libraries.return_value = libraries
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
    assert hass.states.get("sensor.documents_size").state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_library_deleted")
async def test_library_deleted_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fix flow removes the library with its device and entities."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None
    assert dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    http_client = await hass_client()
    data = await start_repair_fix_flow(http_client, DOMAIN, ISSUE_ID)
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {"name": "Documents"}

    data = await process_repair_fix_flow(http_client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert SUBENTRY_ID not in mock_config_entry.subentries
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_library_deleted")
async def test_issue_removed_with_subentry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue is removed when the library subentry is removed manually."""
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None

    assert hass.config_entries.async_remove_subentry(mock_config_entry, SUBENTRY_ID)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


@pytest.mark.usefixtures("mock_library_deleted")
async def test_issue_removed_with_config_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue is removed when the config entry is removed."""
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
