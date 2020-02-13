"""Test Dynalite bridge."""
from unittest.mock import Mock, call, patch

from dynalite_lib import CONF_ALL

from homeassistant.components.dynalite import DATA_CONFIGS, DOMAIN
from homeassistant.components.dynalite.bridge import DynaliteBridge

from tests.common import mock_coro


async def test_bridge_setup():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)

    with patch.object(
        dyn_bridge.dynalite_devices, "async_setup", return_value=mock_coro(True)
    ):
        assert await dyn_bridge.async_setup() is True

    forward_entries = set(
        c[1][1] for c in hass.config_entries.async_forward_entry_setup.mock_calls
    )
    hass.config_entries.async_forward_entry_setup.assert_called_once()
    assert forward_entries == set(["light"])


async def test_update_device():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)
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
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)
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
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)

    device1 = Mock()
    device1.category = "light"
    device2 = Mock()
    device2.category = "switch"
    reg_func = Mock()
    dyn_bridge.register_add_devices(reg_func)
    dyn_bridge.add_devices_when_registered([device1, device2])
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0] is device1


async def test_async_reset():
    """Test async_reset."""
    hass = Mock()
    hass.config_entries.async_forward_entry_unload = Mock(
        return_value=mock_coro(Mock())
    )
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)
    await dyn_bridge.async_reset()
    hass.config_entries.async_forward_entry_unload.assert_called_once()
    assert hass.config_entries.async_forward_entry_unload.mock_calls[0] == call(
        entry, "light"
    )
