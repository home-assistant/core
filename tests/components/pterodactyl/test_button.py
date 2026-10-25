"""Tests for the button platform of the Pterodactyl integration."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.pterodactyl.api import PterodactylCommand
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import SERVER_1_IDENTIFIER

BUTTON_COMMANDS = [
    ("start_server", PterodactylCommand.START_SERVER),
    ("stop_server", PterodactylCommand.STOP_SERVER),
    ("restart_server", PterodactylCommand.RESTART_SERVER),
    ("force_stop_server", PterodactylCommand.FORCE_STOP_SERVER),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_pterodactyl")
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button."""
    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.BUTTON]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        assert len(hass.states.async_all(Platform.BUTTON)) == 8
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_button_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button disabled by default."""
    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.BUTTON]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        entity_id_server1 = "button.test_server_1_force_stop_server"
        entity_id_server2 = "button.test_server_2_force_stop_server"
        entry_server1 = entity_registry.async_get(entity_id_server1)
        entry_server2 = entity_registry.async_get(entity_id_server2)

        assert len(hass.states.async_all(Platform.BUTTON)) == 6
        assert entry_server1
        assert entry_server1.disabled
        assert entry_server1.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entry_server2
        assert entry_server2.disabled
        assert entry_server2.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_pterodactyl")
@pytest.mark.usefixtures("suspended_game_servers")
async def test_button_unavailable_when_suspended(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test button availability when the game server is suspended."""
    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.BUTTON]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        for entity_id in (
            "button.test_server_1_start_server",
            "button.test_server_2_start_server",
        ):
            state = hass.states.get(entity_id)
            assert state
            assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(("button", "command"), BUTTON_COMMANDS)
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: AsyncMock,
    button: str,
    command: PterodactylCommand,
) -> None:
    """Test button press."""
    mock_pterodactyl.client.servers.send_power_action = AsyncMock()

    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.BUTTON]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        entity_id = f"button.test_server_1_{button}"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mock_pterodactyl.client.servers.send_power_action.assert_awaited_once_with(
            SERVER_1_IDENTIFIER, command
        )


@pytest.mark.parametrize(
    ("status", "expected_message"),
    [
        pytest.param(
            500,
            "Failed to send action 'start_server': Connection error",
            id="connection",
        ),
        pytest.param(
            401,
            "Failed to send action 'start_server': Unauthorized",
            id="authorization",
        ),
    ],
)
async def test_button_press_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: AsyncMock,
    status: int,
    expected_message: str,
) -> None:
    """Test button press error handling."""
    mock_pterodactyl.client.servers.send_power_action = AsyncMock(
        side_effect=ClientResponseError(request_info=None, history=[], status=status)
    )

    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.BUTTON]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        entity_id = "button.test_server_1_start_server"
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert str(err.value) == expected_message
        mock_pterodactyl.client.servers.send_power_action.assert_awaited_once_with(
            SERVER_1_IDENTIFIER, PterodactylCommand.START_SERVER
        )
