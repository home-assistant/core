"""Test the Ruckus Unleashed config flow."""
from pyruckus.exceptions import AuthenticationError

from homeassistant.components.ruckus_unleashed import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)

from tests.async_mock import patch
from tests.components.ruckus_unleashed import init_integration, mock_config_entry


async def test_setup_entry_login_error(hass):
    """Test entry setup failed due to login error."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus",
        side_effect=AuthenticationError,
    ):
        entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_setup_entry_connection_error(hass):
    """Test entry setup failed due to connection error."""
    entry = mock_config_entry()
    with patch(
        "homeassistant.components.ruckus_unleashed.Ruckus",
        side_effect=ConnectionError,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
