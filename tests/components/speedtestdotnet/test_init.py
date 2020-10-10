"""Tests for SpeedTest integration."""
import speedtest

from homeassistant import config_entries
from homeassistant.components import speedtestdotnet
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_setup_with_config(hass):
    """Test that we import the config and setup the integration."""
    config = {
        speedtestdotnet.DOMAIN: {
            speedtestdotnet.CONF_SERVER_ID: "1",
            speedtestdotnet.CONF_MANUAL: True,
            speedtestdotnet.CONF_SCAN_INTERVAL: "00:01:00",
        }
    }
    with patch("speedtest.Speedtest"):
        assert await async_setup_component(hass, speedtestdotnet.DOMAIN, config)


async def test_successful_config_entry(hass):
    """Test that SpeedTestDotNet is configured successfully."""

    entry = MockConfigEntry(
        domain=speedtestdotnet.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest"), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_LOADED
    assert forward_entry_setup.mock_calls[0][1] == (
        entry,
        "sensor",
    )


async def test_setup_failed(hass):
    """Test SpeedTestDotNet failed due to an error."""

    entry = MockConfigEntry(
        domain=speedtestdotnet.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest", side_effect=speedtest.ConfigRetrievalError):

        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test removing SpeedTestDotNet."""
    entry = MockConfigEntry(
        domain=speedtestdotnet.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with patch("speedtest.Speedtest"):
        await hass.config_entries.async_setup(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert speedtestdotnet.DOMAIN not in hass.data
