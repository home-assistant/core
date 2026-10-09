"""Tests for the System Bridge switch platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.discord_control import DiscordAction, DiscordControl
from systembridgeconnector.models.fixtures.modules.discord import FIXTURE_DISCORD
from systembridgeconnector.models.response import Response

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "switch.hostname_discord_mute"


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_switch_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the switch platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "service", "action"),
    [
        pytest.param(ENTITY_ID, SERVICE_TURN_ON, DiscordAction.MUTE, id="mute"),
        pytest.param(ENTITY_ID, SERVICE_TURN_OFF, DiscordAction.UNMUTE, id="unmute"),
        pytest.param(
            "switch.hostname_discord_deafen",
            SERVICE_TURN_ON,
            DiscordAction.DEAFEN,
            id="deafen",
        ),
        pytest.param(
            "switch.hostname_discord_deafen",
            SERVICE_TURN_OFF,
            DiscordAction.UNDEAFEN,
            id="undeafen",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_actions(
    hass: HomeAssistant,
    mock_websocket_client: AsyncMock,
    entity_id: str,
    service: str,
    action: DiscordAction,
) -> None:
    """Test switch actions send the Discord control command."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_websocket_client.discord_control.assert_called_once_with(
        DiscordControl(action=action, value=None)
    )


@pytest.mark.parametrize(
    ("side_effect", "return_value", "match"),
    [
        pytest.param(
            ConnectionClosedException,
            None,
            "A connection error occurred",
            id="connection_closed",
        ),
        pytest.param(
            None,
            Response(
                id=FIXTURE_REQUEST_ID,
                type=EventType.ERROR,
                message="Discord is not connected",
                data={},
            ),
            "Failed to control Discord on TestSystem \\(127.0.0.1\\): Discord is not connected",
            id="error_response",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_action_error(
    hass: HomeAssistant,
    mock_websocket_client: AsyncMock,
    side_effect: type[Exception] | None,
    return_value: Response | None,
    match: str,
) -> None:
    """Test switch action errors."""
    mock_websocket_client.discord_control.side_effect = side_effect
    mock_websocket_client.discord_control.return_value = return_value

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    "discord",
    [
        pytest.param(replace(FIXTURE_DISCORD, connected=False), id="not_connected"),
        pytest.param(
            replace(FIXTURE_DISCORD, authenticated=False), id="not_authenticated"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    discord: object,
) -> None:
    """Test the switch is unavailable when Discord is not ready."""
    await mock_config_entry.runtime_data.async_handle_module("discord", discord)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
