"""Tests for the Transport for London integration."""

from unittest.mock import patch
from urllib.error import URLError

from homeassistant.components.tfl.const import (
    CONF_API_APP_KEY,
    CONF_STOP_POINTS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: ["AAAAAAAA1"],
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="unique_id", data=data, options=data
    )

    with patch(
        "homeassistant.components.tfl.stopPoint.getCategories",
        return_value={},
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == data
    assert config_entry.options == data


async def test_config_not_ready_when_connection_failure(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to TfL does not succeed."""

    data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: ["AAAAAAAA1"],
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="unique_id", data=data, options=data
    )

    with patch(
        "homeassistant.components.tfl.stopPoint.getCategories",
        side_effect=URLError("A URL Connection Error"),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert config_entry.data == data
        assert config_entry.options == data
