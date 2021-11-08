"""Tests for 1-Wire config flow."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_owproxy_mock_devices

from tests.common import mock_device_registry, mock_registry


@pytest.mark.usefixtures("owproxy_with_connerror")
async def test_owserver_connect_failure(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test connection failure raises ConfigEntryNotReady."""
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


@patch("homeassistant.components.onewire.PLATFORMS", [SENSOR_DOMAIN])
async def test_registry_cleanup(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock
):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    # Initialise with two components
    setup_owproxy_mock_devices(
        owproxy, SENSOR_DOMAIN, ["10.111111111111", "28.111111111111"]
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 2
    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 2

    # Second item has disappeared from bus, and was removed manually from the front-end
    setup_owproxy_mock_devices(owproxy, SENSOR_DOMAIN, ["10.111111111111"])
    entity_registry.async_remove("sensor.28_111111111111_temperature")
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 1
    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 2

    # Second item has disappeared from bus, and was removed manually from the front-end
    await hass.config_entries.async_reload("2")
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(entity_registry, "2")) == 1
    assert len(dr.async_entries_for_config_entry(device_registry, "2")) == 1
