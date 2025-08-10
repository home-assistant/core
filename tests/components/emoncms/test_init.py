"""Test Emoncms component setup process."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.emoncms.const import DOMAIN, FEED_ID, FEED_NAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import setup_integration
from .conftest import EMONCMS_FAILURE, FEEDS

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emoncms_client: AsyncMock,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emoncms_client: AsyncMock,
) -> None:
    """Test load failure."""
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_migrate_uuid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test migration from home assistant uuid to emoncms uuid."""
    config_entry.add_to_hass(hass)
    assert config_entry.unique_id is None
    for _, feed in enumerate(FEEDS):
        entity_registry.async_get_or_create(
            Platform.SENSOR,
            DOMAIN,
            f"{config_entry.entry_id}-{feed[FEED_ID]}",
            config_entry=config_entry,
            suggested_object_id=f"{DOMAIN}_{feed[FEED_NAME]}",
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    emoncms_uuid = emoncms_client.async_get_uuid.return_value
    assert config_entry.unique_id == emoncms_uuid
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for nb, feed in enumerate(FEEDS):
        assert entity_entries[nb].unique_id == f"{emoncms_uuid}-{feed[FEED_ID]}"
        assert (
            entity_entries[nb].previous_unique_id
            == f"{config_entry.entry_id}-{feed[FEED_ID]}"
        )


async def test_no_uuid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test an issue is created when the emoncms server does not ship an uuid."""
    emoncms_client.async_get_uuid.return_value = None
    await setup_integration(hass, config_entry)

    assert issue_registry.async_get_issue(domain=DOMAIN, issue_id="migrate database")
