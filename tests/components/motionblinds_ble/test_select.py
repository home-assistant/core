"""Tests for Motionblinds BLE selects."""

from enum import Enum
from typing import Any
from unittest.mock import patch

from motionblindsble.const import MotionSpeedLevel
from motionblindsble.device import MotionDevice
import pytest

from homeassistant.components.motionblinds_ble.const import ATTR_SPEED, DOMAIN
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize(("select", "args"), [(ATTR_SPEED, MotionSpeedLevel.HIGH)])
async def test_select(hass: HomeAssistant, select: str, args: Any) -> None:
    """Test select."""

    _, name = await setup_integration(hass)

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
    ("select", "update_func", "value"),
    [(ATTR_SPEED, lambda device: device.update_speed, MotionSpeedLevel.HIGH)],
)
async def test_select_update(
    hass: HomeAssistant, select: str, update_func, value: type[Enum]
) -> None:
    """Test select state update."""

    config_entry, name = await setup_integration(hass)

    device: MotionDevice = hass.data[DOMAIN][config_entry.entry_id]
    update_func(device)(value)
    assert hass.states.get(f"select.{name}_{select}").state == str(value.value)

    await hass.async_block_till_done()
