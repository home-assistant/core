"""Tests for the Roku integration."""
from socket import gaierror as SocketGIAError

from asynctest import patch
from requests.exceptions import RequestException
from requests_mock import Mocker
from roku import RokuException

from homeassistant.components.roku.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.roku import setup_integration


async def test_config_entry_not_ready(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test the Roku configuration entry not ready."""
    with patch(
        "homeassistant.components.roku.Roku._call", side_effect=RokuException,
    ):
        entry = await setup_integration(hass, requests_mock)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_entry_not_ready_request(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test the Roku configuration entry not ready."""
    with patch(
        "homeassistant.components.roku.Roku._call", side_effect=RequestException,
    ):
        entry = await setup_integration(hass, requests_mock)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_entry_not_ready_socket(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test the Roku configuration entry not ready."""
    with patch(
        "homeassistant.components.roku.Roku._call", side_effect=SocketGIAError,
    ):
        entry = await setup_integration(hass, requests_mock)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test the Roku configuration entry unloading."""
    with patch(
        "homeassistant.components.roku.media_player.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.roku.remote.async_setup_entry", return_value=True,
    ):
        entry = await setup_integration(hass, requests_mock)

    assert hass.data[DOMAIN][entry.entry_id]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED
