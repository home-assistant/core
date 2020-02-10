"""Test Dynalite light."""
from unittest.mock import Mock, call, patch

from homeassistant.components.dynalite import DOMAIN
from homeassistant.components.dynalite.light import DynaliteLight, async_setup_entry

from tests.common import mock_coro


async def test_light_setup():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    async_add = Mock()
    bridge = Mock()
    hass.data = {DOMAIN: {entry.entry_id: bridge}}
    await async_setup_entry(hass, entry, async_add)
    bridge.register_add_entities.assert_called_once()
    assert bridge.register_add_entities.mock_calls[0] == call(async_add)


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
    with patch.object(dyn_light, "hass"):
        with patch.object(dyn_light, "schedule_update_ha_state") as update_ha:
            dyn_light.try_schedule_ha()
            update_ha.assert_called_once()
