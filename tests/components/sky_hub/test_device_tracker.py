"""Tests for the Sky Hub device tracker."""

from unittest.mock import MagicMock

from homeassistant.components.sky_hub.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST

from tests.common import MockConfigEntry


async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skyqhub: MagicMock,
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
    assert any(eid.startswith("device_tracker.my_phone") for eid in entity_ids)
    assert any(eid.startswith("device_tracker.my_laptop") for eid in entity_ids)


async def test_legacy_platform_imports_config_entry(
    hass: HomeAssistant, mock_skyqhub: MagicMock
) -> None:
    """Test the legacy device_tracker platform imports a config entry."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, CONF_HOST: MOCK_HOST}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_HOST: MOCK_HOST}
    assert entries[0].source == SOURCE_IMPORT


async def test_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant, mock_skyqhub: MagicMock, issue_registry: IssueRegistry
) -> None:
    """Test an issue is raised when the legacy YAML import cannot connect."""
    mock_skyqhub.return_value.async_get_skyhub_data.return_value = None

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, CONF_HOST: MOCK_HOST}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_HOST}
