"""Test Dynalite bridge."""
from unittest.mock import Mock, patch
import pytest

from homeassistant.components.dynalite import DOMAIN, DATA_CONFIGS
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
    dyn_bridge._dynalite_devices = Mock()

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


# async def test_bridge_setup_invalid_username():
# """Test we start config flow if username is no longer whitelisted."""
# hass = Mock()
# entry = Mock()
# entry.data = {"host": "1.2.3.4", "username": "mock-username"}
# hue_bridge = bridge.HueBridge(hass, entry, False, False)

# with patch.object(bridge, "get_bridge", side_effect=errors.AuthenticationRequired):
# assert await hue_bridge.async_setup() is False

# assert len(hass.async_create_task.mock_calls) == 1
# assert len(hass.config_entries.flow.async_init.mock_calls) == 1
# assert hass.config_entries.flow.async_init.mock_calls[0][2]["data"] == {
# "host": "1.2.3.4"
# }


# async def test_bridge_setup_timeout(hass):
# """Test we retry to connect if we cannot connect."""
# hass = Mock()
# entry = Mock()
# entry.data = {"host": "1.2.3.4", "username": "mock-username"}
# hue_bridge = bridge.HueBridge(hass, entry, False, False)

# with patch.object(
# bridge, "get_bridge", side_effect=errors.CannotConnect
# ), pytest.raises(ConfigEntryNotReady):
# await hue_bridge.async_setup()


# async def test_reset_if_entry_had_wrong_auth():
# """Test calling reset when the entry contained wrong auth."""
# hass = Mock()
# entry = Mock()
# entry.data = {"host": "1.2.3.4", "username": "mock-username"}
# hue_bridge = bridge.HueBridge(hass, entry, False, False)

# with patch.object(bridge, "get_bridge", side_effect=errors.AuthenticationRequired):
# assert await hue_bridge.async_setup() is False

# assert len(hass.async_create_task.mock_calls) == 1

# assert await hue_bridge.async_reset()


# async def test_reset_unloads_entry_if_setup():
# """Test calling reset while the entry has been setup."""
# hass = Mock()
# entry = Mock()
# entry.data = {"host": "1.2.3.4", "username": "mock-username"}
# hue_bridge = bridge.HueBridge(hass, entry, False, False)

# with patch.object(bridge, "get_bridge", return_value=mock_coro(Mock())):
# assert await hue_bridge.async_setup() is True

# assert len(hass.services.async_register.mock_calls) == 1
# assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 3

# hass.config_entries.async_forward_entry_unload.return_value = mock_coro(True)
# assert await hue_bridge.async_reset()

# assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 3
# assert len(hass.services.async_remove.mock_calls) == 1
