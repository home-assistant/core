"""Tests for the Bambu Lab select platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from aiobambulab import BambuLabConnectionError, PrintState, SpeedProfile
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

PRINT_SPEED = "select.x1_carbon_print_speed"


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_selects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the select of a printer."""
    with patch("homeassistant.components.bambu_lab._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("profile", list(SpeedProfile))
async def test_select_option(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    profile: SpeedProfile,
) -> None:
    """Test selecting a speed sends the command to the printer."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PRINT_SPEED, ATTR_OPTION: profile.value},
        blocking=True,
    )

    mock_bambu_lab_client.set_speed_profile.assert_awaited_once_with(profile)


async def test_update(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select follows what the printer pushes."""
    await setup_integration(hass, mock_config_entry)

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, speed_profile=SpeedProfile.LUDICROUS
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_SPEED).state == "ludicrous"

    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, speed_profile=None
    )
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_SPEED).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"print_state": PrintState.PAUSED}, id="paused"),
        pytest.param({"print_state": PrintState.IDLE}, id="idle"),
        pytest.param({"print_state": None}, id="unknown"),
        pytest.param({"accepts_commands": False}, id="no_developer_mode"),
    ],
)
async def test_unavailable(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    changes: dict[str, PrintState | bool | None],
) -> None:
    """Test the select is only available while the printer can change speed."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(PRINT_SPEED).state == "standard"

    mock_bambu_lab_client.state = replace(mock_bambu_lab_client.state, **changes)
    push_update(mock_bambu_lab_client)
    await hass.async_block_till_done()

    assert hass.states.get(PRINT_SPEED).state == STATE_UNAVAILABLE


async def test_command_error(
    hass: HomeAssistant,
    mock_bambu_lab_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the command cannot be sent."""
    await setup_integration(hass, mock_config_entry)
    mock_bambu_lab_client.set_speed_profile.side_effect = BambuLabConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: PRINT_SPEED, ATTR_OPTION: "sport"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"
