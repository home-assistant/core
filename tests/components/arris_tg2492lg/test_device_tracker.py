"""Tests for Arris TG2492LG device tracker."""

from aiohttp import ClientError

from homeassistant import config_entries
from homeassistant.components.arris_tg2492lg.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST, MOCK_PASSWORD


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_connect_box,
    entity_registry: EntityRegistry,
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Only the two online devices should get entities; the offline one is skipped.
    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "arris_tg2492lg"
    ]
    assert len(entries) == 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entity_id.startswith("device_tracker.my_phone") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.my_laptop") for entity_id in entity_ids
    )


async def test_setup_scanner_legacy_platform_imports_config_entry(
    hass: HomeAssistant,
    mock_connect_box,
) -> None:
    """Test legacy device tracker setup triggers config flow import."""
    config = {CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD}

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **config}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == config
    assert entries[0].source == config_entries.SOURCE_IMPORT


async def test_setup_scanner_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant, mock_connect_box, issue_registry: IssueRegistry
) -> None:
    """Test that issue is created when legacy device tracker setup cannot connect."""
    config = {CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD}

    mock_connect_box.return_value.async_login.side_effect = ClientError("fail")

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **config}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")

    assert len(issue_registry.issues) == 1
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_HOST}
