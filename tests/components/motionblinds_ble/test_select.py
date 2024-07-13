"""Tests for Motionblinds BLE selects."""

from enum import Enum
from typing import Any
from unittest.mock import Mock, patch

from motionblindsble.const import MotionSpeedLevel
import pytest

from homeassistant.components.motionblinds_ble.const import ATTR_SPEED
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(("select", "args"), [(ATTR_SPEED, MotionSpeedLevel.HIGH)])
async def test_select(
    mock_config_entry: MockConfigEntry, hass: HomeAssistant, select: str, args: Any
) -> None:
    """Test select."""

    name = await setup_integration(hass, mock_config_entry)

    with patch(
        f"homeassistant.components.motionblinds_ble.MotionDevice.{select}"
    ) as command:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: f"select.{name}_{select}",
                ATTR_OPTION: MotionSpeedLevel.HIGH.value,
            },
            blocking=True,
        )
        command.assert_called_once_with(args)

    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("select", "register_callback", "value"),
    [
        (
            ATTR_SPEED,
            lambda device: device.register_speed_callback,
            MotionSpeedLevel.HIGH,
        )
    ],
)
async def test_select_update(
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    hass: HomeAssistant,
    select: str,
    register_callback,
    value: type[Enum],
) -> None:
    """Test select state update."""

    await setup_integration(hass, mock_config_entry)

    update_func = register_callback(mock_motion_device).call_args[0][0]

    update_func(value)
    assert hass.states.get(f"select.{select}").state == str(value.value)
