"""Tests for the Jellyfin remote platform."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.remote import (
    DOMAIN as R_DOMAIN,
    RemoteService,
    RemoteServiceArgument,
)
from homeassistant.const import STATE_ON, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_remote(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test the Jellyfin remote."""
    state = hass.states.get("remote.jellyfin_device")
    state2 = hass.states.get("remote.jellyfin_device_two")
    state3 = hass.states.get("remote.jellyfin_device_three")
    state4 = hass.states.get("remote.jellyfin_device_four")

    assert state
    assert state2
    # Doesn't support remote control; remote not created
    assert state3 is None
    assert state4

    assert state.state == STATE_ON


async def test_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test Jellyfin remote services."""
    state = hass.states.get("remote.jellyfin_device")
    assert state

    command = "Select"
    await hass.services.async_call(
        R_DOMAIN,
        RemoteService.SEND_COMMAND,
        {
            TargetKey.ENTITY_ID: state.entity_id,
            RemoteServiceArgument.COMMAND: command,
            RemoteServiceArgument.NUM_REPEATS: 1,
            RemoteServiceArgument.DELAY_SECS: 0,
            RemoteServiceArgument.HOLD_SECS: 0,
        },
        blocking=True,
    )
    assert len(mock_api.command.mock_calls) == 1
    assert mock_api.command.mock_calls[0].args == (
        "SESSION-UUID",
        command,
    )

    command = "MoveLeft"
    await hass.services.async_call(
        R_DOMAIN,
        RemoteService.SEND_COMMAND,
        {
            TargetKey.ENTITY_ID: state.entity_id,
            RemoteServiceArgument.COMMAND: command,
            RemoteServiceArgument.NUM_REPEATS: 2,
            RemoteServiceArgument.DELAY_SECS: 0,
            RemoteServiceArgument.HOLD_SECS: 0,
        },
        blocking=True,
    )
    assert len(mock_api.command.mock_calls) == 3
    assert mock_api.command.mock_calls[1].args == (
        "SESSION-UUID",
        command,
    )
    assert mock_api.command.mock_calls[2].args == (
        "SESSION-UUID",
        command,
    )
