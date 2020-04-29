"""Test Hue bridge."""
from asynctest import CoroutineMock, Mock, patch
import pytest

from homeassistant.components.hue import bridge, errors
from homeassistant.exceptions import ConfigEntryNotReady


async def test_bridge_setup(hass):
    """Test a successful setup."""
    entry = Mock()
    api = Mock(initialize=CoroutineMock())
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch("aiohue.Bridge", return_value=api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.api is api
    assert len(mock_forward.mock_calls) == 3
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    assert forward_entries == {"light", "binary_sensor", "sensor"}


async def test_bridge_setup_invalid_username(hass):
    """Test we start config flow if username is no longer whitelisted."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch.object(
        bridge, "authenticate_bridge", side_effect=errors.AuthenticationRequired
    ), patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await hue_bridge.async_setup() is False

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][2]["data"] == {"host": "1.2.3.4"}


async def test_bridge_setup_timeout(hass):
    """Test we retry to connect if we cannot connect."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch.object(
        bridge, "authenticate_bridge", side_effect=errors.CannotConnect
    ), pytest.raises(ConfigEntryNotReady):
        await hue_bridge.async_setup()


async def test_reset_if_entry_had_wrong_auth(hass):
    """Test calling reset when the entry contained wrong auth."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch.object(
        bridge, "authenticate_bridge", side_effect=errors.AuthenticationRequired
    ), patch.object(bridge, "create_config_flow") as mock_create:
        assert await hue_bridge.async_setup() is False

    assert len(mock_create.mock_calls) == 1

    assert await hue_bridge.async_reset()


async def test_reset_unloads_entry_if_setup(hass):
    """Test calling reset while the entry has been setup."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch.object(bridge, "authenticate_bridge", return_value=Mock()), patch(
        "aiohue.Bridge", return_value=Mock()
    ), patch.object(hass.config_entries, "async_forward_entry_setup") as mock_forward:
        assert await hue_bridge.async_setup() is True

    assert len(hass.services.async_services()) == 1
    assert len(mock_forward.mock_calls) == 3

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        assert await hue_bridge.async_reset()

    assert len(mock_forward.mock_calls) == 3
    assert len(hass.services.async_services()) == 0


async def test_handle_unauthorized(hass):
    """Test handling an unauthorized error on update."""
    entry = Mock(async_setup=CoroutineMock())
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    hue_bridge = bridge.HueBridge(hass, entry, False, False)

    with patch.object(bridge, "authenticate_bridge", return_value=Mock()), patch(
        "aiohue.Bridge", return_value=Mock()
    ):
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.authorized is True

    with patch.object(bridge, "create_config_flow") as mock_create:
        await hue_bridge.handle_unauthorized_error()

    assert hue_bridge.authorized is False
    assert len(mock_create.mock_calls) == 1
    assert mock_create.mock_calls[0][1][1] == "1.2.3.4"
