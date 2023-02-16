"""Test the Litter-Robot update entity."""
from unittest.mock import AsyncMock, MagicMock

from pylitterbot import LitterRobot4
import pytest

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration

ENTITY_ID = "update.test_firmware"
OLD_FIRMWARE = "ESP: 1.1.50 / PIC: 10512.2560.2.53 / TOF: 4.0.65.4"
NEW_FIRMWARE = "ESP: 1.1.51 / PIC: 10512.2560.2.53 / TOF: 4.0.65.4"


async def test_robot_with_no_update(
    hass: HomeAssistant, mock_account_with_litterrobot_4: MagicMock
) -> None:
    """Tests the update entity was set up."""
    robot: LitterRobot4 = mock_account_with_litterrobot_4.robots[0]
    robot.has_firmware_update = AsyncMock(return_value=False)
    robot.get_latest_firmware = AsyncMock(return_value=None)

    entry = await setup_integration(
        hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == OLD_FIRMWARE
    assert state.attributes[ATTR_LATEST_VERSION] == OLD_FIRMWARE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_robot_with_update(
    hass: HomeAssistant, mock_account_with_litterrobot_4: MagicMock
) -> None:
    """Tests the update entity was set up."""
    robot: LitterRobot4 = mock_account_with_litterrobot_4.robots[0]
    robot.has_firmware_update = AsyncMock(return_value=True)
    robot.get_latest_firmware = AsyncMock(return_value=NEW_FIRMWARE)

    await setup_integration(hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == OLD_FIRMWARE
    assert state.attributes[ATTR_LATEST_VERSION] == NEW_FIRMWARE

    robot.update_firmware = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert robot.update_firmware.call_count == 1

    robot.update_firmware = AsyncMock(return_value=True)
    await hass.services.async_call(
        PLATFORM_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    assert robot.update_firmware.call_count == 1


async def test_robot_with_update_already_in_progress(
    hass: HomeAssistant, mock_account_with_litterrobot_4: MagicMock
) -> None:
    """Tests the update entity was set up."""
    robot: LitterRobot4 = mock_account_with_litterrobot_4.robots[0]
    robot._update_data({"isFirmwareUpdateTriggered": True}, partial=True)

    entry = await setup_integration(
        hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == OLD_FIRMWARE
    assert state.attributes[ATTR_LATEST_VERSION] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
