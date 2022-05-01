"""Test for Sensibo component Init."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.sensibo.util import NoUsernameError
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrate entry unique id."""
    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        config_entry = await init_integration(hass, version=1, unique_id="1234567890")

    assert config_entry.state == config_entries.ConfigEntryState.LOADED
    assert config_entry.version == 2
    assert config_entry.unique_id == "username"


async def test_migrate_entry_fails(hass: HomeAssistant) -> None:
    """Test migrate entry unique id."""
    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        side_effect=NoUsernameError("No username returned"),
    ):
        config_entry = await init_integration(hass, version=1, unique_id="1234567890")

    assert config_entry.state == config_entries.ConfigEntryState.MIGRATION_ERROR
    assert config_entry.version == 1
    assert config_entry.unique_id == "1234567890"


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
