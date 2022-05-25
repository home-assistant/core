"""Test for SQL component Init."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    with patch("homeassistant.components.sql.remove_configured_db_url_if_not_needed"):
        config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    with patch("homeassistant.components.sql.remove_configured_db_url_if_not_needed"):
        config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_remove_configured_db_url_if_not_needed_when_not_needed(
    hass: HomeAssistant,
    recorder_mock,
):
    """Test configured db_url is replaced with None if matching the recorder db."""
    recorder_db_url = get_instance(hass).db_url

    config = {
        "db_url": recorder_db_url,
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "count_tables",
    }

    config_entry = await init_integration(hass, config)

    assert config_entry.options.get("db_url") is None


async def test_remove_configured_db_url_if_not_needed_when_needed(
    hass: HomeAssistant,
    recorder_mock,
):
    """Test configured db_url is not replaced if it differs from the recorder db."""
    db_url = "mssql://"

    config = {
        "db_url": db_url,
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "count_tables",
    }

    config_entry = await init_integration(hass, config)

    assert config_entry.options.get("db_url") == db_url
