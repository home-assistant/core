"""Tests for 1-Wire config flow."""
import logging
from unittest.mock import MagicMock

from pyownet import protocol
import pytest

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("owproxy_with_connerror")
async def test_owserver_connect_failure(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test connection failure raises ConfigEntryNotReady."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_owserver_listing_failure(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock
):
    """Test listing failure raises ConfigEntryNotReady."""
    owproxy.return_value.dir.side_effect = protocol.OwnetError()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("owproxy")
async def test_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test being able to unload an entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("sysbus")
async def test_warning_no_devices(
    hass: HomeAssistant,
    sysbus_config_entry: ConfigEntry,
    caplog: pytest.LogCaptureFixture,
):
    """Test warning is generated when no sysbus devices found."""
    with caplog.at_level(logging.WARNING, logger="homeassistant.components.onewire"):
        await hass.config_entries.async_setup(sysbus_config_entry.entry_id)
        await hass.async_block_till_done()
        assert "No onewire sensor found. Check if dtoverlay=w1-gpio" in caplog.text


@pytest.mark.usefixtures("sysbus")
async def test_unload_sysbus_entry(
    hass: HomeAssistant, sysbus_config_entry: ConfigEntry
):
    """Test being able to unload an entry."""
    await hass.config_entries.async_setup(sysbus_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert sysbus_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(sysbus_config_entry.entry_id)
    await hass.async_block_till_done()

    assert sysbus_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
