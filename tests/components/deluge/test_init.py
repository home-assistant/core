"""Tests for Deluge init."""

from unittest.mock import patch

import pytest


from homeassistant.components import deluge
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro

MOCK_ENTRY = MockConfigEntry(
    domain=deluge.DOMAIN,
    data={
        deluge.CONF_NAME: "Deluge",
        deluge.CONF_HOST: "0.0.0.0",
        deluge.CONF_USERNAME: "user",
        deluge.CONF_PASSWORD: "pass",
        deluge.CONF_PORT: 5555,
    },
)


@pytest.fixture(name="api")
def mock_deluge_api():
    """Mock an api."""
    with patch("deluge_client.DelugeRPCClient.connect"):
        yield


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a Deluge client."""
    assert await async_setup_component(hass, deluge.DOMAIN, {}) is True
    assert deluge.DOMAIN not in hass.data


async def test_setup_with_config(hass, api):
    """Test that we import the config and setup the client."""
    config = {
        deluge.DOMAIN: {
            deluge.CONF_NAME: "Deluge",
            deluge.CONF_HOST: "0.0.0.0",
            deluge.CONF_USERNAME: "user",
            deluge.CONF_PASSWORD: "pass",
            deluge.CONF_PORT: 5555,
        },
        deluge.DOMAIN: {
            deluge.CONF_NAME: "Deluge2",
            deluge.CONF_HOST: "0.0.0.1",
            deluge.CONF_USERNAME: "user",
            deluge.CONF_PASSWORD: "pass",
            deluge.CONF_PORT: 5555,
        },
    }
    assert await async_setup_component(hass, deluge.DOMAIN, config) is True


async def test_successful_config_entry(hass, api):
    """Test that configured Deluge is configured successfully."""

    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    with patch.object(
        deluge.DelugeData, "init_torrent_list", return_value=True
    ), patch.object(deluge.DelugeData, "update", return_value=True):
        assert await deluge.async_setup_entry(hass, entry) is True
        assert entry.options == {
            deluge.CONF_SCAN_INTERVAL: deluge.DEFAULT_SCAN_INTERVAL
        }


async def test_setup_failed(hass):
    """Test Deluge failed due to an error."""

    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    # test connection error raising ConfigEntryNotReady
    with patch(
        "deluge_client.DelugeRPCClient.connect", side_effect=ConnectionRefusedError,
    ), pytest.raises(ConfigEntryNotReady):

        await deluge.async_setup_entry(hass, entry)

    # test Authentication error returning false

    with patch(
        "deluge_client.DelugeRPCClient.connect",
        side_effect=Exception("Username does not exist"),
    ):

        assert await deluge.async_setup_entry(hass, entry) is False


async def test_unload_entry(hass, api):
    """Test removing transmission client."""
    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
    ) as unload_entry, patch.object(
        deluge.DelugeData, "init_torrent_list", return_value=True
    ), patch.object(
        deluge.DelugeData, "update", return_value=True
    ):
        assert await deluge.async_setup_entry(hass, entry)

        assert await deluge.async_unload_entry(hass, entry)
        assert unload_entry.call_count == 2
        assert entry.entry_id not in hass.data[deluge.DOMAIN]
