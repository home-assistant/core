"""Tests for Vanderbilt SPC component."""

from unittest.mock import PropertyMock

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.spc.const import SIGNAL_UPDATE_ALARM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher

from .conftest import ALARM_MODE_MAPPING


@pytest.mark.parametrize(("user", "mode", "expected_state"), ALARM_MODE_MAPPING)
async def test_update_alarm_device(
    hass: HomeAssistant, mock_config, mock_area, user, mode, expected_state
) -> None:
    """Test that alarm panel state changes on incoming websocket data."""
    entity_id = "alarm_control_panel.house"

    mock_area.mode = mode
    mock_area.last_changed_by = user

    dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(mock_area.id))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["changed_by"] == user


async def test_alarm_modes(
    hass: HomeAssistant, mock_config, mock_area, mock_client, alarm_mode
) -> None:
    """Test all alarm modes."""
    service, mode, expected_state = alarm_mode
    entity_id = "alarm_control_panel.house"

    await hass.services.async_call(
        "alarm_control_panel",
        service,
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_client.return_value.change_mode.assert_called_once_with(
        area=mock_area, new_mode=mode
    )


async def test_alarm_triggered(hass: HomeAssistant, mock_config, mock_area) -> None:
    """Test alarm triggered state."""
    entity_id = "alarm_control_panel.house"

    type(mock_area).verified_alarm = PropertyMock(return_value=True)
    dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(mock_area.id))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == AlarmControlPanelState.TRIGGERED
