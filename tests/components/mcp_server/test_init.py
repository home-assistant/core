"""Test the Model Context Protocol Server init module."""

from homeassistant.components.mcp_server.const import CONF_REQUIRE_ADMIN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


async def test_init(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the integration is initialized and can be unloaded cleanly."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry_require_admin(hass: HomeAssistant) -> None:
    """Test an entry created before the require admin option keeps the endpoints open."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    assert config_entry.minor_version == 2
    assert config_entry.data == {
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_REQUIRE_ADMIN: False,
    }


async def test_migrate_entry_keeps_require_admin(hass: HomeAssistant) -> None:
    """Test the migration keeps an option the options flow saved before it ran."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LLM_HASS_API: [llm.LLM_API_ASSIST], CONF_REQUIRE_ADMIN: True},
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    assert config_entry.minor_version == 2
    assert config_entry.data[CONF_REQUIRE_ADMIN] is True
