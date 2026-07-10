"""Tests for the DD-WRT device tracker."""

from unittest.mock import MagicMock

from homeassistant.components.ddwrt.const import DOMAIN
from homeassistant.components.ddwrt.router import DdWrtConnectionError
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device tracker entities are created from coordinator data."""
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
    assert any(
        entity_id.startswith("device_tracker.my_phone") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.my_laptop") for entity_id in entity_ids
    )


async def test_setup_entry_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
) -> None:
    """Test the config entry retries setup when the router cannot be reached."""
    mock_router.return_value.get_clients.side_effect = DdWrtConnectionError("fail")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_legacy_platform_imports_config_entry(
    hass: HomeAssistant, mock_router: MagicMock
) -> None:
    """Test the legacy device tracker platform imports a config entry."""
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
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy platform creates a repair issue when it cannot connect."""
    mock_router.return_value.get_clients.side_effect = DdWrtConnectionError("fail")

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_CONFIG["host"]}
