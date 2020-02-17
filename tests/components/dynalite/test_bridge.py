"""Test Dynalite bridge."""
from unittest.mock import Mock, call

from asynctest import patch
from dynalite_lib import CONF_ALL
import pytest

from homeassistant.components import dynalite


@pytest.fixture
def dyn_bridge():
    """Define a basic mock bridge."""
    hass = Mock()
    host = "1.2.3.4"
    bridge = dynalite.DynaliteBridge(hass, {dynalite.CONF_HOST: host})
    return bridge


async def test_update_device(dyn_bridge):
    """Test a successful setup."""
    async_dispatch = Mock()

    with patch(
        "homeassistant.components.dynalite.bridge.async_dispatcher_send", async_dispatch
    ):
        dyn_bridge.update_device(CONF_ALL)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(
            dyn_bridge.hass, f"dynalite-update-{dyn_bridge.host}"
        )
        async_dispatch.reset_mock()
        device = Mock
        device.unique_id = "abcdef"
        dyn_bridge.update_device(device)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(
            dyn_bridge.hass, f"dynalite-update-{dyn_bridge.host}-{device.unique_id}"
        )


async def test_add_devices_then_register(dyn_bridge):
    """Test that add_devices work."""
    # First test empty
    dyn_bridge.add_devices_when_registered([])
    assert not dyn_bridge.waiting_devices
    # Now with devices
    device1 = Mock()
    device1.category = "light"
    device2 = Mock()
    device2.category = "switch"
    dyn_bridge.add_devices_when_registered([device1, device2])
    reg_func = Mock()
    dyn_bridge.register_add_devices(reg_func)
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0] is device1


async def test_register_then_add_devices(dyn_bridge):
    """Test that add_devices work after register_add_entities."""
    device1 = Mock()
    device1.category = "light"
    device2 = Mock()
    device2.category = "switch"
    reg_func = Mock()
    dyn_bridge.register_add_devices(reg_func)
    dyn_bridge.add_devices_when_registered([device1, device2])
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0] is device1


async def test_try_connection(dyn_bridge):
    """Test that try connection works."""
    # successful
    with patch.object(dyn_bridge.dynalite_devices, "connected", True):
        assert await dyn_bridge.try_connection()
    # unsuccessful
    with patch.object(dyn_bridge.dynalite_devices, "connected", False), patch(
        "homeassistant.components.dynalite.bridge.CONNECT_INTERVAL", 0
    ):
        assert not await dyn_bridge.try_connection()
