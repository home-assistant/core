"""Test Dynalite light."""
from unittest.mock import Mock, call, patch

from homeassistant.components.dynalite import DOMAIN
from homeassistant.components.dynalite.light import DynaliteLight, async_setup_entry
from homeassistant.components.light import SUPPORT_BRIGHTNESS

from tests.common import mock_coro


async def test_light_setup():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    async_add = Mock()
    bridge = Mock()
    hass.data = {DOMAIN: {entry.entry_id: bridge}}
    await async_setup_entry(hass, entry, async_add)
    bridge.register_add_devices.assert_called_once()
    internal_func = bridge.register_add_devices.mock_calls[0][1][0]
    device = Mock()
    device.category = "light"
    internal_func([device])
    async_add.assert_called_once()
    assert async_add.mock_calls[0][1][0][0].device == device


async def test_light():
    """Test the light entity."""
    device = Mock()
    device.async_turn_on = Mock(return_value=mock_coro(Mock()))
    device.async_turn_off = Mock(return_value=mock_coro(Mock()))
    bridge = Mock()
    dyn_light = DynaliteLight(device, bridge)
    assert dyn_light.name is device.name
    assert dyn_light.unique_id is device.unique_id
    assert dyn_light.available is device.available
    assert dyn_light.hidden is device.hidden
    await dyn_light.async_update()  # does nothing
    assert dyn_light.device_info is device.device_info
    assert dyn_light.brightness is device.brightness
    assert dyn_light.is_on is device.is_on
    await dyn_light.async_turn_on(aaa="bbb")
    assert device.async_turn_on.mock_calls[0] == call(aaa="bbb")
    await dyn_light.async_turn_off(ccc="ddd")
    assert device.async_turn_off.mock_calls[0] == call(ccc="ddd")


async def test_supported_features():
    """Test supported feaures didn't change."""
    device = Mock()
    bridge = Mock()
    dyn_light = DynaliteLight(device, bridge)
    assert dyn_light.supported_features == SUPPORT_BRIGHTNESS


async def test_added_to_ha():
    """Test registration to dispatch when added."""

    def temp_signal(device=None):
        if device:
            return "yes"
        return "no"

    device = Mock()
    bridge = Mock()
    bridge.update_signal = temp_signal
    dyn_light = DynaliteLight(device, bridge)
    async_dispatch = Mock()
    with patch(
        "homeassistant.components.dynalite.light.async_dispatcher_connect",
        async_dispatch,
    ):
        await dyn_light.async_added_to_hass()
        assert async_dispatch.call_count == 2
        assert async_dispatch.mock_calls[0] == call(
            dyn_light.hass, temp_signal("aaa"), dyn_light.schedule_update_ha_state
        )
        assert async_dispatch.mock_calls[1] == call(
            dyn_light.hass, temp_signal(), dyn_light.schedule_update_ha_state
        )
