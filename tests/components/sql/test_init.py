"""Test for SQL component Init."""
from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.sql import validate_sql_select
from homeassistant.components.sql.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import YAML_CONFIG_INVALID, YAML_CONFIG_NO_DB, init_integration


async def test_setup_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


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
