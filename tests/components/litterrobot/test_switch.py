"""Test the Litter-Robot switch entity."""

from unittest.mock import MagicMock, patch

from pylitterbot import FeederRobot, Robot
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import snapshot_platform

NIGHT_LIGHT_MODE_ENTITY_ID = "switch.test_night_light_mode"
PANEL_LOCKOUT_ENTITY_ID = "switch.test_panel_lockout"


async def test_switch(
    hass: HomeAssistant, mock_account: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Tests the switch entity was set up."""
    await setup_integration(hass, mock_account, SWITCH_DOMAIN)

    state = hass.states.get(NIGHT_LIGHT_MODE_ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    entity_entry = entity_registry.async_get(NIGHT_LIGHT_MODE_ENTITY_ID)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize(
    ("entity_id", "robot_command", "updated_field"),
    [
        (NIGHT_LIGHT_MODE_ENTITY_ID, "set_night_light", "nightLightActive"),
        (PANEL_LOCKOUT_ENTITY_ID, "set_panel_lockout", "panelLockActive"),
    ],
)
async def test_on_off_commands(
    hass: HomeAssistant,
    mock_account: MagicMock,
    entity_id: str,
    robot_command: str,
    updated_field: str,
) -> None:
    """Test sending commands to the switch."""
    await setup_integration(hass, mock_account, SWITCH_DOMAIN)
    robot: Robot = mock_account.robots[0]

    state = hass.states.get(entity_id)
    assert state

    data = {ATTR_ENTITY_ID: entity_id}

    services = ((SERVICE_TURN_ON, STATE_ON, "1"), (SERVICE_TURN_OFF, STATE_OFF, "0"))
    for count, (service, new_state, new_value) in enumerate(services):
        await hass.services.async_call(SWITCH_DOMAIN, service, data, blocking=True)
        robot._update_data({updated_field: new_value}, partial=True)

        assert getattr(robot, robot_command).call_count == count + 1
        assert (state := hass.states.get(entity_id))
        assert state.state == new_state


async def test_feeder_robot_switch(
    hass: HomeAssistant, mock_account_with_feederrobot: MagicMock
) -> None:
    """Tests Feeder-Robot switches."""
    await setup_integration(hass, mock_account_with_feederrobot, SWITCH_DOMAIN)
    robot: FeederRobot = mock_account_with_feederrobot.robots[0]

    gravity_mode_switch = "switch.test_gravity_mode"

    switch = hass.states.get(gravity_mode_switch)
    assert switch.state == STATE_OFF

    data = {ATTR_ENTITY_ID: gravity_mode_switch}

    services = ((SERVICE_TURN_ON, STATE_ON, True), (SERVICE_TURN_OFF, STATE_OFF, False))
    for count, (service, new_state, new_value) in enumerate(services):
        await hass.services.async_call(SWITCH_DOMAIN, service, data, blocking=True)
        robot._update_data({"state": {"info": {"gravity": new_value}}}, partial=True)

        assert robot.set_gravity_mode.call_count == count + 1
        assert (state := hass.states.get(gravity_mode_switch))
        assert state.state == new_state


async def test_switch_command_exception(
    hass: HomeAssistant, mock_account_with_side_effects: MagicMock
) -> None:
    """Test that LitterRobotException is wrapped in HomeAssistantError."""
    await setup_integration(hass, mock_account_with_side_effects, SWITCH_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: NIGHT_LIGHT_MODE_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Litter-Robot 5 switch entities."""
    with patch("homeassistant.components.litterrobot.PLATFORMS", [Platform.SWITCH]):
        entry = await setup_integration(hass, mock_account_with_litterrobot_5)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "state", "service", "expected_value", "expected_day"),
    [
        pytest.param(
            "switch.test_sunday_sleep_mode",
            STATE_ON,
            SERVICE_TURN_OFF,
            False,
            0,
            id="sunday_turn_off",
        ),
        pytest.param(
            "switch.test_friday_sleep_mode",
            STATE_OFF,
            SERVICE_TURN_ON,
            True,
            5,
            id="friday_turn_on",
        ),
    ],
)
async def test_litter_robot_5_sleep_mode_switches(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_id: str,
    state: str,
    service: str,
    expected_value: bool,
    expected_day: int,
) -> None:
    """Tests the Litter-Robot 5 per-day sleep mode switches."""
    await setup_integration(hass, mock_account_with_litterrobot_5, SWITCH_DOMAIN)

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == state

    robot = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(
        expected_value, day_of_week=expected_day
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_sleep_mode_switch_failed(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test that a rejected sleep mode update raises HomeAssistantError."""
    await setup_integration(hass, mock_account_with_litterrobot_5, SWITCH_DOMAIN)

    robot = mock_account_with_litterrobot_5.robots[0]
    robot.set_sleep_mode.return_value = False

    with pytest.raises(HomeAssistantError, match="Unable to update"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_friday_sleep_mode"},
            blocking=True,
        )
