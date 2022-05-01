"""Test for Sensibo component Init."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.sensibo.util import NoUsernameError
from homeassistant.core import HomeAssistant

from . import init_integration
from .response import DATA_FROM_API


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = await init_integration(hass, entry_id="setup_entry")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrate entry unique id."""
    entry = await init_integration(hass, version=1, unique_id="1234567890")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == "username"


async def test_migrate_entry_fails(hass: HomeAssistant) -> None:
    """Test migrate entry unique id."""
    entry = await init_integration(hass, version=1, unique_id="1234567890")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        side_effect=NoUsernameError("No username returned"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert entry.unique_id == "1234567890"


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    entry = await init_integration(hass, entry_id="unload_entry")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
