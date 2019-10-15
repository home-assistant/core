"""Test Dynalite bridge."""
from unittest.mock import Mock, patch
import pytest

from homeassistant.components.dynalite import DOMAIN, DATA_CONFIGS  # , LOGGER
from homeassistant.components.dynalite.bridge import DynaliteBridge, BridgeError


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
        dyn_bridge._dynalite_devices, "async_setup", return_value=mock_coro(Mock())
    ):
        assert await dyn_bridge.async_setup() is True

    forward_entries = set(
        c[1][1] for c in hass.config_entries.async_forward_entry_setup.mock_calls
    )
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1
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


async def test_add_devices_and_then_regiter_add_entities():
    """Test that add_devices work."""
    hass = Mock()
    entry = Mock()
    host = "1.2.3.4"
    entry.data = {"host": host}
    hass.data = {DOMAIN: {DATA_CONFIGS: {host: {}}}}
    dyn_bridge = DynaliteBridge(hass, entry)

    with patch.object(
        dyn_bridge._dynalite_devices, "async_setup", return_value=mock_coro(Mock())
    ):
        assert await dyn_bridge.async_setup() is True
        device1 = Mock()
        device1.category = "light"
        device2 = Mock()
        device2.category = "switch"
        dyn_bridge.add_devices([device1, device2])
        reg_func = Mock()
        dyn_bridge.register_add_entities(reg_func)
    reg_func.assert_called_once()
    assert reg_func.call_args[0][0][0]._device is device1
