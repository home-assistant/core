"""Tests for the Bambu Lab button platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from aiobambulab import BambuLabConnectionError, PrintState
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

PAUSE_PRINT = "button.x1_carbon_pause_print"
RESUME_PRINT = "button.x1_carbon_resume_print"
STOP_PRINT = "button.x1_carbon_stop_print"


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_buttons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the buttons of a printer."""
    with patch("homeassistant.components.bambu_lab._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("print_state", "entity_id", "method"),
    [
        pytest.param(PrintState.PRINTING, PAUSE_PRINT, "pause_print", id="pause"),
        pytest.param(PrintState.PAUSED, RESUME_PRINT, "resume_print", id="resume"),
        pytest.param(PrintState.PRINTING, STOP_PRINT, "stop_print", id="stop"),
        pytest.param(
            PrintState.PAUSED, STOP_PRINT, "stop_print", id="stop_while_paused"
        ),
    ],
)
async def test_press(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    print_state: PrintState,
    entity_id: str,
    method: str,
) -> None:
    """Test pressing a button sends the command to the printer."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, print_state=print_state
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    getattr(mock_bambu_lab_client, method).assert_awaited_once_with()


@pytest.mark.parametrize(
    ("print_state", "available"),
    [
        pytest.param(PrintState.IDLE, set(), id="idle"),
        pytest.param(PrintState.PREPARING, set(), id="preparing"),
        pytest.param(PrintState.PRINTING, {PAUSE_PRINT, STOP_PRINT}, id="printing"),
        pytest.param(PrintState.PAUSED, {RESUME_PRINT, STOP_PRINT}, id="paused"),
        pytest.param(PrintState.FINISHED, set(), id="finished"),
        pytest.param(None, set(), id="unknown"),
    ],
)
async def test_available_for_print_state(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    print_state: PrintState | None,
    available: set[str],
) -> None:
    """Test a button is only available when the printer can do what it asks."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, print_state=print_state
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert {
        entity_id
        for entity_id in (PAUSE_PRINT, RESUME_PRINT, STOP_PRINT)
        if hass.states.get(entity_id).state != STATE_UNAVAILABLE
    } == available


async def test_unavailable_without_developer_mode(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the buttons are unavailable while the printer accepts no commands."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, accepts_commands=False
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PAUSE_PRINT).state == STATE_UNAVAILABLE
    assert hass.states.get(STOP_PRINT).state == STATE_UNAVAILABLE

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, accepts_commands=True
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PAUSE_PRINT).state != STATE_UNAVAILABLE
    assert hass.states.get(STOP_PRINT).state != STATE_UNAVAILABLE


async def test_command_error(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the command cannot be sent."""
    await setup_integration(hass, mock_config_entry)
    mock_bambu_lab_client.pause_print.side_effect = BambuLabConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: PAUSE_PRINT}, blocking=True
        )

    assert exc_info.value.translation_key == "command_error"
