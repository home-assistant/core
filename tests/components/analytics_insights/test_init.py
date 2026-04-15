"""Test the Home Assistant analytics init module."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.analytics_insights import CONF_TRACKED_APPS
from homeassistant.components.analytics_insights.const import (
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_analytics_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_migration_v1_to_v2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_analytics_client: AsyncMock,
) -> None:
    """Test migration from version 1 to 2 change to app_."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Home Assistant Analytics migration time!",
        data={},
        options={
            "tracked_addons": ["core_samba"],
            CONF_TRACKED_INTEGRATIONS: ["youtube"],
        },
    )
    entry.add_to_hass(hass)
    assert entry.version == 1

    # This should update
    addon_entity_samba = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="addon_core_samba_active_installations",
        config_entry=entry,
        original_name="Samba Active Installations",
    )

    # This should NOT update
    core_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="core_youtube_active_installations",
        config_entry=entry,
        original_name="YouTube Active Installations",
    )

    assert addon_entity_samba.unique_id == "addon_core_samba_active_installations"
    assert core_entity.unique_id == "core_youtube_active_installations"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2

    addon_entity_samba_after = entity_registry.async_get(addon_entity_samba.entity_id)
    core_entity_after = entity_registry.async_get(core_entity.entity_id)

    assert addon_entity_samba_after.unique_id == "app_core_samba_active_installations"
    assert core_entity_after.unique_id == "core_youtube_active_installations"

    assert "tracked_addons" not in entry.options
    assert entry.options[CONF_TRACKED_APPS] == ["core_samba"]
