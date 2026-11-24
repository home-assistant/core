"""Tests for JVC Projector remote platform."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    RemoteService,
    RemoteServiceArgument,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "remote.jvc_projector"


async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity_registry.async_get(entity.entity_id)


@patch("homeassistant.components.jvc_projector.remote.POWER_SLEEP", 0)
async def test_commands(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test service call are called."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.SEND_COMMAND,
        {TargetKey.ENTITY_ID: ENTITY_ID, RemoteServiceArgument.COMMAND: ["ok"]},
        blocking=True,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.SEND_COMMAND,
        {TargetKey.ENTITY_ID: ENTITY_ID, RemoteServiceArgument.COMMAND: ["hdmi1"]},
        blocking=True,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.SEND_COMMAND,
        {TargetKey.ENTITY_ID: ENTITY_ID, RemoteServiceArgument.COMMAND: ["anamo"]},
        blocking=True,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        RemoteService.SEND_COMMAND,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            RemoteServiceArgument.COMMAND: ["picture_mode"],
        },
        blocking=True,
    )
    assert mock_device.remote.call_count == 4


async def test_unknown_command(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test unknown service call errors."""
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            RemoteService.SEND_COMMAND,
            {TargetKey.ENTITY_ID: ENTITY_ID, RemoteServiceArgument.COMMAND: ["bad"]},
            blocking=True,
        )
    assert str(err.value) == "bad is not a known command"
