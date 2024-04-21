"""Test for SQL component Init."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.util import get_instance
from homeassistant.components.sql import validate_sql_select
from homeassistant.components.sql.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import YAML_CONFIG_INVALID, YAML_CONFIG_NO_DB, init_integration


async def test_setup_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_config(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup from yaml config."""
    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG_NO_DB)
        await hass.async_block_till_done()


async def test_setup_invalid_config(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test setup from yaml with invalid config."""
    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        assert not await async_setup_component(hass, DOMAIN, YAML_CONFIG_INVALID)
        await hass.async_block_till_done()


async def test_invalid_query(hass: HomeAssistant) -> None:
    """Test invalid query."""
    with pytest.raises(vol.Invalid):
        validate_sql_select("DROP TABLE *")

    with pytest.raises(vol.Invalid):
        validate_sql_select("SELECT5 as value")

    with pytest.raises(vol.Invalid):
        validate_sql_select(";;")


async def test_query_no_read_only(hass: HomeAssistant) -> None:
    """Test query no read only."""
    with pytest.raises(vol.Invalid):
        validate_sql_select("UPDATE states SET state = 999999 WHERE state_id = 11125")


async def test_query_no_read_only_cte(hass: HomeAssistant) -> None:
    """Test query no read only CTE."""
    with pytest.raises(vol.Invalid):
        validate_sql_select(
            "WITH test AS (SELECT state FROM states) UPDATE states SET states.state = test.state;"
        )


async def test_multiple_queries(hass: HomeAssistant) -> None:
    """Test multiple queries."""
    with pytest.raises(vol.Invalid):
        validate_sql_select("SELECT 5 as value; UPDATE states SET state = 10;")


async def test_remove_configured_db_url_if_not_needed_when_not_needed(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
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
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
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
