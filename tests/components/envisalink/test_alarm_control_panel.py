"""Tests for the Envisalink alarm control panel."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant

from .conftest import ALARM_ENTITY, DOMAIN, MOCK_CODE, MOCK_CONFIG, setup_envisalink


@pytest.mark.parametrize(
    ("status_overrides", "expected_state"),
    [
        ({"alarm": True}, AlarmControlPanelState.TRIGGERED),
        ({"armed_zero_entry_delay": True}, AlarmControlPanelState.ARMED_NIGHT),
        ({"armed_away": True}, AlarmControlPanelState.ARMED_AWAY),
        ({"armed_stay": True}, AlarmControlPanelState.ARMED_HOME),
        ({"exit_delay": True}, AlarmControlPanelState.ARMING),
        ({"entry_delay": True}, AlarmControlPanelState.PENDING),
        ({}, AlarmControlPanelState.DISARMED),
        ({"alpha": ""}, STATE_UNKNOWN),
    ],
)
async def test_alarm_states(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    status_overrides: dict[str, bool | str],
    expected_state: str,
) -> None:
    """Test the partition status maps to the correct alarm state."""
    assert await setup_envisalink(hass)

    status = mock_controller.alarm_state["partition"][1]["status"]
    status.update(status_overrides)
    mock_controller.callback_partition_state_change(1)
    await hass.async_block_till_done()

    assert hass.states.get(ALARM_ENTITY).state == expected_state


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_ALARM_ARM_HOME, "arm_stay_partition"),
        (SERVICE_ALARM_ARM_AWAY, "arm_away_partition"),
        (SERVICE_ALARM_ARM_NIGHT, "arm_night_partition"),
        (SERVICE_ALARM_DISARM, "disarm_partition"),
    ],
)
async def test_arm_disarm_commands(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    service: str,
    method: str,
) -> None:
    """Test arm/disarm services call the controller with code and partition.

    No code is supplied in the call: the keypad is hidden when a code is
    configured, so HA injects the configured default code. This proves the
    default-code path, not just an echo of a code we passed in.
    """
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        Platform.ALARM_CONTROL_PANEL,
        service,
        {"entity_id": ALARM_ENTITY},
        blocking=True,
    )

    getattr(mock_controller, method).assert_called_once_with(MOCK_CODE, 1)


async def test_trigger_calls_panic(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the trigger service fires a panic alarm of the configured type."""
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        Platform.ALARM_CONTROL_PANEL,
        SERVICE_ALARM_TRIGGER,
        {"entity_id": ALARM_ENTITY},
        blocking=True,
    )

    # "Police" is the default panic type when none is configured.
    mock_controller.panic_alarm.assert_called_once_with("Police")


async def test_code_format_with_configured_code(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the keypad is hidden (no code_format) when a code is configured."""
    assert await setup_envisalink(hass)

    assert hass.states.get(ALARM_ENTITY).attributes.get("code_format") is None


async def test_code_format_without_configured_code(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the numeric keypad shows when no code is configured."""
    config = deepcopy(MOCK_CONFIG)
    del config[DOMAIN]["code"]
    assert await setup_envisalink(hass, config)

    assert hass.states.get(ALARM_ENTITY).attributes["code_format"] == CodeFormat.NUMBER


async def test_partition_update_filtering(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test partition updates are filtered by number; None applies to all."""
    assert await setup_envisalink(hass)
    status = mock_controller.alarm_state["partition"][1]["status"]
    status["alarm"] = True

    # Update targeting a different partition is ignored (stays disarmed).
    mock_controller.callback_partition_state_change(2)
    await hass.async_block_till_done()
    assert hass.states.get(ALARM_ENTITY).state == AlarmControlPanelState.DISARMED

    # A matching partition delivered as a string is coerced and applies.
    mock_controller.callback_partition_state_change("1")
    await hass.async_block_till_done()
    assert hass.states.get(ALARM_ENTITY).state == AlarmControlPanelState.TRIGGERED

    # A None partition applies to every entity.
    status["alarm"] = False
    mock_controller.callback_partition_state_change(None)
    await hass.async_block_till_done()
    assert hass.states.get(ALARM_ENTITY).state == AlarmControlPanelState.DISARMED


async def test_alarm_keypress_service(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the custom alarm_keypress service forwards to the partition."""
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        DOMAIN,
        "alarm_keypress",
        {"entity_id": ALARM_ENTITY, "keypress": "*71"},
        blocking=True,
    )

    mock_controller.keypresses_to_partition.assert_called_once_with(1, "*71")
