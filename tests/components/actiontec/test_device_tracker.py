"""Tests for the Actiontec device tracker."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.actiontec.const import DOMAIN
from homeassistant.components.actiontec.device_tracker import async_setup_scanner
from homeassistant.components.actiontec.model import Device
from homeassistant.components.device_tracker.const import ScannerEntityStateAttribute
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG, MOCK_DEVICES, MOCK_HOST

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_actiontec_data: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test device tracker entities are created from the coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == DOMAIN
    ]
    assert len(entries) == 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(eid.startswith("device_tracker.192_168_1_10") for eid in entity_ids)
    assert any(eid.startswith("device_tracker.192_168_1_11") for eid in entity_ids)

    entries_by_mac = {entry.unique_id: entry for entry in entries}
    assert entries_by_mac.keys() == {
        "AA:BB:CC:DD:EE:FF",
        "11:22:33:44:55:66",
    }

    state = hass.states.get(entries_by_mac["AA:BB:CC:DD:EE:FF"].entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes[ScannerEntityStateAttribute.IP] == "192.168.1.10"
    assert state.attributes[ScannerEntityStateAttribute.MAC] == "AA:BB:CC:DD:EE:FF"

    mock_get_actiontec_data.return_value = [MOCK_DEVICES[1]]
    await mock_config_entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entries_by_mac["AA:BB:CC:DD:EE:FF"].entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert ScannerEntityStateAttribute.IP not in state.attributes
    assert state.attributes[ScannerEntityStateAttribute.MAC] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.usefixtures("mock_get_actiontec_data")
async def test_legacy_platform_imports_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test the legacy device_tracker platform imports a config entry."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == MOCK_CONFIG
    assert entries[0].source == SOURCE_IMPORT


async def test_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant,
    mock_get_actiontec_data: MagicMock,
    issue_registry: IssueRegistry,
) -> None:
    """Test an issue is raised when the legacy YAML import cannot connect."""
    mock_get_actiontec_data.return_value = None

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_HOST}


async def test_setup_entry_retries_when_router_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_actiontec_data: MagicMock,
) -> None:
    """Test the config entry retries when the router returns no data."""
    mock_get_actiontec_data.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_filters_expired_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_actiontec_data: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test expired devices are not added as connected scanner entities."""
    expired = Device("192.168.1.12", "22:33:44:55:66:77", -120)
    mock_get_actiontec_data.return_value = [*MOCK_DEVICES, expired]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == DOMAIN
    ]
    assert len(entries) == 2


async def test_legacy_import_clears_stale_cannot_connect_issue(
    hass: HomeAssistant,
    mock_get_actiontec_data: MagicMock,
    issue_registry: IssueRegistry,
) -> None:
    """Test a successful YAML import removes a stale cannot_connect repair issue."""
    mock_get_actiontec_data.return_value = None
    assert not await async_setup_scanner(hass, MOCK_CONFIG, AsyncMock())
    assert (
        issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect") is not None
    )

    mock_get_actiontec_data.return_value = MOCK_DEVICES
    assert await async_setup_scanner(hass, MOCK_CONFIG, AsyncMock())
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect") is None
