"""Test for the alarm control panel const module."""

from typing import Any

import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import (
    ATTR_CODE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .conftest import MockAlarmControlPanel


async def help_test_async_alarm_control_panel_service(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    code: str | None | UndefinedType = UNDEFINED,
) -> None:
    """Help to lock a test lock."""
    data: dict[str, Any] = {"entity_id": entity_id}
    if code is not UNDEFINED:
        data[ATTR_CODE] = code

    await hass.services.async_call(
        alarm_control_panel.DOMAIN, service, data, blocking=True
    )
    await hass.async_block_till_done()


async def test_set_mock_alarm_control_panel_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test mock attributes and default code stored in the registry."""
    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "1234"},
    )
    await hass.async_block_till_done()

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code
        == "1234"
    )
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state is not None
    assert state.attributes["code_format"] == CodeFormat.NUMBER
    assert (
        state.attributes["supported_features"]
        == AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
    )


async def test_default_code_option_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test default code stored in the registry is updated."""

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code is None
    )

    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "4321"},
    )
    await hass.async_block_till_done()

    assert (
        mock_alarm_control_panel_entity._alarm_control_panel_option_default_code
        == "4321"
    )


@pytest.mark.parametrize(
    ("code_format", "supported_features"),
    [(CodeFormat.TEXT, AlarmControlPanelEntityFeature.ARM_AWAY)],
)
async def test_alarm_control_panel_arm_with_code(
    hass: HomeAssistant, mock_alarm_control_panel_entity: MockAlarmControlPanel
) -> None:
    """Test alarm control panel entity with open service."""
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state.attributes["code_format"] == CodeFormat.TEXT

    with pytest.raises(ServiceValidationError):
        await help_test_async_alarm_control_panel_service(
            hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
        )
    with pytest.raises(ServiceValidationError):
        await help_test_async_alarm_control_panel_service(
            hass,
            mock_alarm_control_panel_entity.entity_id,
            SERVICE_ALARM_ARM_AWAY,
            code="",
        )
    await help_test_async_alarm_control_panel_service(
        hass,
        mock_alarm_control_panel_entity.entity_id,
        SERVICE_ALARM_ARM_AWAY,
        code="1234",
    )
    assert mock_alarm_control_panel_entity.calls_arm_away.call_count == 1
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with("1234")


@pytest.mark.parametrize(
    ("code_format", "code_arm_required"),
    [(CodeFormat.NUMBER, False)],
)
async def test_alarm_control_panel_with_no_code(
    hass: HomeAssistant, mock_alarm_control_panel_entity: MockAlarmControlPanel
) -> None:
    """Test alarm control panel entity without code."""
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
    )
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_CUSTOM_BYPASS
    )
    mock_alarm_control_panel_entity.calls_arm_custom.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_HOME
    )
    mock_alarm_control_panel_entity.calls_arm_home.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_NIGHT
    )
    mock_alarm_control_panel_entity.calls_arm_night.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_VACATION
    )
    mock_alarm_control_panel_entity.calls_arm_vacation.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_DISARM
    )
    mock_alarm_control_panel_entity.calls_disarm.assert_called_with(None)
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_TRIGGER
    )
    mock_alarm_control_panel_entity.calls_trigger.assert_called_with(None)


@pytest.mark.parametrize(
    ("code_format", "code_arm_required"),
    [(CodeFormat.NUMBER, True)],
)
async def test_alarm_control_panel_with_default_code(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
) -> None:
    """Test alarm control panel entity without code."""
    entity_registry.async_update_entity_options(
        "alarm_control_panel.test_alarm_control_panel",
        "alarm_control_panel",
        {alarm_control_panel.CONF_DEFAULT_CODE: "1234"},
    )
    await hass.async_block_till_done()

    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_AWAY
    )
    mock_alarm_control_panel_entity.calls_arm_away.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_CUSTOM_BYPASS
    )
    mock_alarm_control_panel_entity.calls_arm_custom.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_HOME
    )
    mock_alarm_control_panel_entity.calls_arm_home.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_NIGHT
    )
    mock_alarm_control_panel_entity.calls_arm_night.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_ARM_VACATION
    )
    mock_alarm_control_panel_entity.calls_arm_vacation.assert_called_with("1234")
    await help_test_async_alarm_control_panel_service(
        hass, mock_alarm_control_panel_entity.entity_id, SERVICE_ALARM_DISARM
    )
    mock_alarm_control_panel_entity.calls_disarm.assert_called_with("1234")


async def test_alarm_control_panel_not_log_deprecated_state_warning(
    hass: HomeAssistant,
    mock_alarm_control_panel_entity: MockAlarmControlPanel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test correctly using alarm_state doesn't log issue or raise repair."""
    state = hass.states.get(mock_alarm_control_panel_entity.entity_id)
    assert state is not None
    assert (
        "the 'alarm_state' property and return its state using the AlarmControlPanelState enum"
        not in caplog.text
    )
