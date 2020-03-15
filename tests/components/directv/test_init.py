"""Tests for the Roku integration."""
from asynctest import patch
from requests.exceptions import RequestException

from homeassistant.components.directv.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.directv import MockDirectvClass, setup_integration

# pylint: disable=redefined-outer-name


async def test_config_entry_not_ready(hass: HomeAssistantType) -> None:
    """Test the DirecTV configuration entry not ready."""
    with patch(
        "homeassistant.components.directv.DIRECTV", new=MockDirectvClass,
    ), patch(
        "homeassistant.components.directv.DIRECTV.get_locations",
        side_effect=RequestException,
    ):
        entry = await setup_integration(hass)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(hass: HomeAssistantType) -> None:
    """Test the DirecTV configuration entry unloading."""
    with patch(
        "homeassistant.components.directv.DIRECTV", new=MockDirectvClass,
    ), patch(
        "homeassistant.components.directv.media_player.async_setup_entry",
        return_value=True,
    ):
        entry = await setup_integration(hass)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED
