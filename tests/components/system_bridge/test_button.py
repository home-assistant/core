"""Tests for the System Bridge button platform."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import (
    BadRequestException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.command_execute import ExecuteRequest
from systembridgeconnector.models.command_result import ExecuteResult
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.settings import (
    Settings,
    SettingsCommandDefinition,
    SettingsCommands,
)

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_COMMAND, FIXTURE_REQUEST_ID, FIXTURE_UUID, setup_integration

SHUTDOWN_ENTITY_ID = "button.hostname_shut_down"
COMMAND_ENTITY_ID = "button.hostname_back_up"


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_button_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the button platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        pytest.param("button.hostname_sleep", "power_sleep", id="sleep"),
        pytest.param("button.hostname_hibernate", "power_hibernate", id="hibernate"),
        pytest.param("button.hostname_restart", "power_restart", id="restart"),
        pytest.param(SHUTDOWN_ENTITY_ID, "power_shutdown", id="shutdown"),
        pytest.param("button.hostname_lock", "power_lock", id="lock"),
        pytest.param("button.hostname_log_out", "power_logout", id="logout"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_button(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test pressing a power button sends its power command."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {CommonServiceArgument.ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_websocket_client, method).assert_awaited_once_with()


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [
        pytest.param(
            [
                Response(
                    id=FIXTURE_REQUEST_ID,
                    type=EventType.ERROR,
                    message="Shutdown is not supported",
                    data={},
                )
            ],
            "Failed to send the power command: Shutdown is not supported",
            id="error_response",
        ),
        pytest.param(
            ConnectionClosedException("Connection is closed"),
            "A connection error occurred",
            id="connection_closed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_button_failure(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    side_effect: list[Response] | Exception,
    match: str,
) -> None:
    """Test a failed power command raises."""
    mock_websocket_client.power_shutdown.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: SHUTDOWN_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_command_button(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
) -> None:
    """Test pressing a saved command's button runs it."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {CommonServiceArgument.ENTITY_ID: COMMAND_ENTITY_ID},
        blocking=True,
    )

    mock_websocket_client.execute_command.assert_awaited_once_with(
        ExecuteRequest(commandID=FIXTURE_COMMAND.id)
    )


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [
        pytest.param(
            [
                ExecuteResult(
                    commandID=FIXTURE_COMMAND.id, exitCode=2, stdout="", stderr="no"
                )
            ],
            "Back up exited with code 2",
            id="exit_code",
        ),
        pytest.param(
            [
                ExecuteResult(
                    commandID=FIXTURE_COMMAND.id,
                    exitCode=-1,
                    stdout="",
                    stderr="",
                    error="executable not found",
                )
            ],
            "Failed to run Back up: executable not found",
            id="error",
        ),
        pytest.param(
            BadRequestException("Command not allowed"),
            "Failed to run Back up: Command not allowed",
            id="bad_request",
        ),
        pytest.param(
            ConnectionErrorException("Timeout waiting for command execution response"),
            "Back up didn't finish in time",
            id="timeout",
        ),
        pytest.param(
            ConnectionClosedException("Connection is closed"),
            "A connection error occurred",
            id="connection_closed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_command_button_failure(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    side_effect: list[ExecuteResult] | Exception,
    match: str,
) -> None:
    """Test a saved command that fails raises."""
    mock_websocket_client.execute_command.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: COMMAND_ENTITY_ID},
            blocking=True,
        )


async def test_command_buttons_follow_settings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test buttons are added, renamed and removed as the allowlist changes."""
    settings_callback = mock_websocket_client.listen.call_args.kwargs[
        "settings_callback"
    ]
    lock_screen = SettingsCommandDefinition(id="lock-screen", name="Lock screen")

    await settings_callback(
        Settings(
            commands=SettingsCommands(
                allowlist=[replace(FIXTURE_COMMAND, name="Nightly backup"), lock_screen]
            )
        )
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(COMMAND_ENTITY_ID))
    assert state.attributes[ATTR_FRIENDLY_NAME] == "hostname Nightly backup"
    assert hass.states.get("button.hostname_lock_screen")

    await settings_callback(
        Settings(commands=SettingsCommands(allowlist=[lock_screen]))
    )
    await hass.async_block_till_done()

    assert hass.states.get(COMMAND_ENTITY_ID) is None
    assert entity_registry.async_get(COMMAND_ENTITY_ID) is None
    assert hass.states.get("button.hostname_lock_screen")


async def test_settings_change_while_fetching_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a settings change during the reconnect fetch isn't undone by it."""
    settings_callback = mock_websocket_client.listen.call_args.kwargs[
        "settings_callback"
    ]
    lock_screen = SettingsCommandDefinition(id="lock-screen", name="Lock screen")

    async def fetch_stale() -> SettingsCommands:
        await settings_callback(
            Settings(
                commands=SettingsCommands(allowlist=[FIXTURE_COMMAND, lock_screen])
            )
        )
        return SettingsCommands(allowlist=[FIXTURE_COMMAND])

    mock_websocket_client.connected = False
    mock_websocket_client.get_commands.side_effect = fetch_stale
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("button.hostname_lock_screen")


@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_command_button_deleted_while_stopped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a button whose command was deleted while Home Assistant was stopped goes."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        BUTTON_DOMAIN,
        DOMAIN,
        f"{FIXTURE_UUID}_command_removed",
        config_entry=mock_config_entry,
        suggested_object_id="hostname_removed",
    )

    assert await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("button.hostname_removed") is None
    assert hass.states.get(COMMAND_ENTITY_ID)


async def test_command_buttons_without_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the other buttons still load when the host can't list its commands."""
    mock_websocket_client.get_commands.side_effect = BadRequestException(
        "Unknown event"
    )

    assert await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SHUTDOWN_ENTITY_ID)
    assert hass.states.get(COMMAND_ENTITY_ID) is None
