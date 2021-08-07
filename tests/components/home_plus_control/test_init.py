"""Test the Legrand Home+ Control integration."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.home_plus_control.const import (
    CONF_SUBSCRIPTION_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from tests.components.home_plus_control.conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    SUBSCRIPTION_KEY,
)


async def test_loading(hass, mock_config_entry):
    """Test component loading."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value={},
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()

    assert len(mock_check.mock_calls) == 1
    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED


async def test_loading_with_no_config(hass, mock_config_entry):
    """Test component loading failure when it has not configuration."""
    mock_config_entry.add_to_hass(hass)
    await setup.async_setup_component(hass, DOMAIN, {})
    # Component setup fails because the oauth2 implementation could not be registered
    assert mock_config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR


async def test_unloading(hass, mock_config_entry):
    """Test component unloading."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value={},
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()

    assert len(mock_check.mock_calls) == 1
    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED

    # We now unload the entry
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
