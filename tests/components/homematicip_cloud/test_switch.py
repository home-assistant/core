"""Test HomematicIP Cloud switch devices."""

from unittest.mock import Mock, patch

from homeassistant.setup import async_setup_component
from homeassistant.components import homematicip_cloud as hmipc
from homeassistant.bootstrap import async_setup_component

from tests.common import mock_coro, MockConfigEntry

from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice)
from homeassistant.components.homematicip_cloud.switch import (
    HomematicipSwitch, HomematicipOpenCollector8)


async def test_switch_is_on(hass):
    """Test switch is on HomematicIP Cloud."""

    from homematicip.aio.device import AsyncPlugableSwitch
    connection = Mock()
    home = Mock()
    device = AsyncPlugableSwitch(connection)
    device.on = True
    switch = HomematicipSwitch(home, device)
    assert switch.is_on is True

async def test_switch_turn_on_and_off(hass):
    """Test turning on and off HomematicIP Cloud switch."""

    from homematicip.aio.device import AsyncPlugableSwitch
    connection = Mock()
    home = Mock()
    device = AsyncPlugableSwitch(connection)
    switch = HomematicipSwitch(home, device)
    with patch.object(device, 'set_switch_state',
        return_value = mock_coro(True)):
        await switch.async_turn_on()
        assert device.set_switch_state.called
        await switch.async_turn_off()
        assert device.set_switch_state.called


async def test_switch_turn_on_and_off(hass):
    """Test turning on and off HomematicIP Cloud switch."""

    from homematicip.aio.device import AsyncOpenCollector8Module
    connection = Mock()
    home = Mock()
    device = AsyncOpenCollector8Module(connection)
    switch = HomematicipOpenCollector8(home, device)
    with patch.object(device, 'set_switch_state',
        return_value = mock_coro(True)):
        await switch.async_turn_on()
        assert device.set_switch_state.called
        await switch.async_turn_off()
        assert device.set_switch_state.called
