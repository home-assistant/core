"""Tests for Honeywell switch component."""

from unittest.mock import MagicMock

from aiosomecomfort.exceptions import SomeComfortError
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

from tests.common import MockConfigEntry


async def test_emheat_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device: MagicMock,
) -> None:
    """Test emergency heat switch."""

    await init_integration(hass, config_entry)
    entity_id = f"switch.{device.name}_emergency_heat"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_not_called()

    device.set_system_mode.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_not_called()

    device.system_mode = "heat"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("emheat")

    device.set_system_mode.reset_mock()
    device.system_mode = "emheat"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")

    device.set_system_mode.reset_mock()
    device.system_mode = "heat"
    device.set_system_mode.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("emheat")

    device.set_system_mode.reset_mock()
    device.system_mode = "emheat"
    device.set_system_mode.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("off")
