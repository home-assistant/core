"""Tests for the Aladdin Connect integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
            }
        },
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.OAuth2Session",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test a successful unload entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
            }
        },
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aladdin_connect.config_entry_oauth2_flow.OAuth2Session",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
