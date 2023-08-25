"""Test the IKEA Idasen Desk connection switch."""
import asyncio
from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from . import CONNECTION_SWITCH_ENTITY_ID, init_integration, set_connection_switch

from tests.common import mock_restore_cache


async def test_connect_disconnect_from_service(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test turning the connection on and off."""
    await init_integration(hass)

    # should be on by default
    assert mock_desk_api.is_connected

    await set_connection_switch(hass, False)
    assert not mock_desk_api.is_connected

    await set_connection_switch(hass, True)
    assert mock_desk_api.is_connected


async def test_ensure_connection_state(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test that the switch enforces the expected connection state when the coordinator updates."""
    await init_integration(hass)

    await set_connection_switch(hass, False)
    await mock_desk_api.connect(None)
    await hass.async_block_till_done()
    assert not mock_desk_api.is_connected

    await set_connection_switch(hass, True)
    await mock_desk_api.disconnect()
    await hass.async_block_till_done()
    await asyncio.sleep(0.1)
    assert mock_desk_api.is_connected


@pytest.mark.parametrize(
    ("state", "is_connected"), [(STATE_ON, True), (STATE_OFF, False)]
)
async def test_restore_state(
    hass: HomeAssistant, mock_desk_api: MagicMock, state, is_connected
) -> None:
    """Test restoring the state from cache."""
    mock_restore_cache(
        hass,
        (State(f"{CONNECTION_SWITCH_ENTITY_ID}", state),),
    )
    await init_integration(hass)
    assert mock_desk_api.is_connected == is_connected
