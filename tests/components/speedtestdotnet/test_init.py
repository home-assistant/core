"""Tests for SpeedTest integration."""
# import pytest
import speedtest

from homeassistant import config_entries
from homeassistant.components import speedtestdotnet
from homeassistant.components.speedtestdotnet.const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_SCAN_INTERVAL

from . import MOCK_RESULTS, MOCK_SERVER_LIST

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_successful_config_entry(hass):
    """Test that SpeedTestDotNet is configured successfully."""

    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest"), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == config_entries.ENTRY_STATE_LOADED

        assert hass.data[DOMAIN].scan_interval == DEFAULT_SCAN_INTERVAL
        assert forward_entry_setup.mock_calls[0][1] == (entry, "sensor",)


async def test_setup_failed(hass):
    """Test SpeedTestDotNet failed due to an error."""

    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest", side_effect=speedtest.ConfigRetrievalError):

        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test removing SpeedTestDotNet."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest"):
        await hass.config_entries.async_setup(entry.entry_id)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
        assert speedtestdotnet.DOMAIN not in hass.data


async def test_get_server_id(hass):
    """Test updating data from speedtest."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    # test getting best server_id when no server name is specified
    with patch("speedtest.Speedtest") as mock_api:

        mock_api.return_value.get_best_server.return_value = MOCK_SERVER_LIST[
            "Server1"
        ][0]
        await hass.config_entries.async_setup(entry.entry_id)
        assert hass.data[speedtestdotnet.DOMAIN].get_server_id() == "1"

        # test getting server_id from options if specified
        options = {
            CONF_SERVER_NAME: "Server2",
            CONF_SERVER_ID: "2",
            CONF_MANUAL: False,
            CONF_SCAN_INTERVAL: 60,
        }

        hass.config_entries.async_update_entry(entry, data={}, options=options)

        assert hass.data[speedtestdotnet.DOMAIN].get_server_id() == "2"


async def test_async_update(hass):
    """Test updating data from speedtest."""
    entry = MockConfigEntry(domain=speedtestdotnet.DOMAIN, data={})
    entry.add_to_hass(hass)

    # test getting best server_id when no server name is specified
    with patch("speedtest.Speedtest") as mock_api, patch(
        "homeassistant.components.speedtestdotnet.async_dispatcher_send"
    ) as mock_disptacher:

        mock_api.return_value.get_best_server.return_value = MOCK_SERVER_LIST[
            "Server1"
        ][0]
        mock_api.return_value.results.dict.return_value = MOCK_RESULTS
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.data[speedtestdotnet.DOMAIN].async_update()
        await hass.async_block_till_done()

        assert hass.data[speedtestdotnet.DOMAIN].data == MOCK_RESULTS
        assert len(mock_disptacher.mock_calls) == 1
