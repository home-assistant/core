"""Test Dynalite bridge."""
from unittest.mock import Mock, call

from asynctest import patch
from dynalite_lib import CONF_ALL

from homeassistant.components import dynalite


async def test_bridge_setup():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {dynalite.DOMAIN: {dynalite.DATA_CONFIGS: {host: {}}}}
    dyn_bridge = dynalite.DynaliteBridge(hass, host)

    with patch.object(
        dyn_bridge.dynalite_devices, "async_setup", return_value=True
    ) as dyn_dev_setup:
        assert await dyn_bridge.async_setup() is True
        dyn_dev_setup.assert_called_once
        hass.config_entries.async_forward_entry_setup.assert_not_called()


async def test_update_device():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {dynalite.DOMAIN: {dynalite.DATA_CONFIGS: {host: {}}}}
    dyn_bridge = dynalite.DynaliteBridge(hass, host)
    async_dispatch = Mock()

    with patch(
        "homeassistant.components.dynalite.bridge.async_dispatcher_send", async_dispatch
    ):
        dyn_bridge.update_device(CONF_ALL)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(hass, f"dynalite-update-{host}")
        async_dispatch.reset_mock()
        device = Mock
        device.unique_id = "abcdef"
        dyn_bridge.update_device(device)
        async_dispatch.assert_called_once()
        assert async_dispatch.mock_calls[0] == call(
            hass, f"dynalite-update-{host}-{device.unique_id}"
        )


async def test_add_devices_then_register():
    """Test that add_devices work."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {dynalite.DOMAIN: {dynalite.DATA_CONFIGS: {host: {}}}}
    dyn_bridge = dynalite.DynaliteBridge(hass, host)
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


async def test_register_then_add_devices():
    """Test that add_devices work after register_add_entities."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {dynalite.DOMAIN: {dynalite.DATA_CONFIGS: {host: {}}}}
    dyn_bridge = dynalite.DynaliteBridge(hass, host)

    device1 = Mock()
    device1.category = "light"
    device2 = Mock()
    device2.category = "switch"
    reg_func = Mock()
    dyn_bridge.register_add_devices(reg_func)
    dyn_bridge.add_devices_when_registered([device1, device2])
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0] is device1
