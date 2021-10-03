"""Tests for the comfoconnect initialization."""
from unittest import mock

import pytest

from homeassistant.components.comfoconnect import (
    ComfoConnectBridge,
    async_setup,
    async_setup_entry,
)
from homeassistant.components.comfoconnect.const import DOMAIN
from homeassistant.components.comfoconnect.sensor import (
    ATTR_CURRENT_RMOT,
    ATTR_CURRENT_TEMPERATURE,
)
from homeassistant.const import CONF_HOST, CONF_RESOURCES, CONF_SENSORS
from homeassistant.exceptions import ConfigEntryNotReady


async def test_async_setup_entry(
    mock_comfoconnect_command, mock_bridge, mock_config_entry, hass
):
    """Test async_setup_entry."""
    await async_setup_entry(hass, mock_config_entry)
    await hass.async_block_till_done()
    ccb = hass.data[DOMAIN]
    assert isinstance(ccb, ComfoConnectBridge)


async def test_setup_entry_no_bridges(
    mock_comfoconnect_command, mock_bridge, mock_config_entry, hass
):
    """Test that ConfigurationNotReady is raised if no bridge discovered."""
    with mock.patch("pycomfoconnect.bridge.Bridge.discover") as mock_discover:
        mock_discover.return_value = []
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_async_setup(mock_comfoconnect_command, mock_bridge, hass):
    """Test import during async_setup."""
    config = {
        DOMAIN: {CONF_HOST: "1.2.3.4"},
        "sensor": [
            {
                "platform": DOMAIN,
                CONF_RESOURCES: [ATTR_CURRENT_RMOT, ATTR_CURRENT_TEMPERATURE],
            }
        ],
    }

    await async_setup(hass, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data[CONF_HOST] == "1.2.3.4"
    assert entry.options[CONF_SENSORS] == [ATTR_CURRENT_RMOT, ATTR_CURRENT_TEMPERATURE]


async def test_async_setup_already_imported(mock_config_entry, hass):
    """Test that nothing is imported if config entry already exists."""
    await async_setup(hass, {})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
