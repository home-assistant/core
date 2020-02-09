"""Test Dynalite bridge."""
from unittest.mock import Mock, call, patch

from dynalite_lib import CONF_ALL
import pytest

from homeassistant.components.dynalite import DATA_CONFIGS, DOMAIN
from homeassistant.components.dynalite.bridge import BridgeError, DynaliteBridge

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


async def test_invalid_host():
    """Test without host in hass.data."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {}}}

    dyn_bridge = None
    with pytest.raises(BridgeError):
        dyn_bridge = DynaliteBridge(hass, entry)
    assert dyn_bridge is None


async def test_add_devices_then_register():
    """Test that add_devices work."""
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
    dyn_bridge.add_devices([device1, device2])
    reg_func = Mock()
    dyn_bridge.register_add_entities(reg_func)
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0].device is device1


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
    dyn_bridge.register_add_entities(reg_func)
    dyn_bridge.add_devices([device1, device2])
    reg_func.assert_called_once()
    assert reg_func.mock_calls[0][1][0][0].device is device1


async def test_update_device():
    """Test the update_device callback."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)
    with patch.object(dyn_bridge, "dynalite_devices") as devices_mock:
        # Single device update
        device1 = Mock()
        device1.unique_id = "testing1"
        device2 = Mock()
        device2.unique_id = "testing2"
        dyn_bridge.all_entities = {
            device1.unique_id: device1,
            device2.unique_id: device2,
        }
        dyn_bridge.update_device(device1)
        device1.try_schedule_ha.assert_called_once()
        device2.try_schedule_ha.assert_not_called()
        # connected to network - all devices update
        devices_mock.available = True
        dyn_bridge.update_device(CONF_ALL)
        assert device1.try_schedule_ha.call_count == 2
        device2.try_schedule_ha.assert_called_once()
        # disconnected from network - all devices update
        devices_mock.available = False
        dyn_bridge.update_device(CONF_ALL)
        assert device1.try_schedule_ha.call_count == 3
        assert device2.try_schedule_ha.call_count == 2


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
