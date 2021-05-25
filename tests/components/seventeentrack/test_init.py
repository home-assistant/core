"""Tests for SpeedTest integration."""
from unittest.mock import AsyncMock

from py17track.errors import SeventeenTrackError

from homeassistant import config_entries
from homeassistant.components.seventeentrack.const import DOMAIN
from homeassistant.setup import async_setup_component

from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a controller."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test that Seventeentrack is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_LOADED


async def test_setup_failed(hass, mock_api):
    """Test Seventeentrack failed due to failed authentication."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="user",
    )
    entry.add_to_hass(hass)

    mock_api.return_value.login = AsyncMock(return_value=False)
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_SETUP_ERROR


async def test_setup_retry(hass, mock_api):
    """Test Seventeentrack setup retry due to unknown error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="user",
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = SeventeenTrackError
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test removing Seventeentrack."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert DOMAIN not in hass.data
