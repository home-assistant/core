"""Test Hue bridge."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import bridge, errors
from homeassistant.components.hue.const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
)
from homeassistant.exceptions import ConfigEntryNotReady


async def test_bridge_setup(hass):
    """Test a successful setup."""
    entry = Mock()
    api = Mock(initialize=AsyncMock())
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

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
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

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
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

    with patch.object(
        bridge, "authenticate_bridge", side_effect=errors.CannotConnect
    ), pytest.raises(ConfigEntryNotReady):
        await hue_bridge.async_setup()


async def test_reset_if_entry_had_wrong_auth(hass):
    """Test calling reset when the entry contained wrong auth."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

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
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

    with patch.object(bridge, "authenticate_bridge", return_value=Mock()), patch(
        "aiohue.Bridge", return_value=Mock()
    ), patch.object(hass.config_entries, "async_forward_entry_setup") as mock_forward:
        assert await hue_bridge.async_setup() is True

    assert len(hass.services.async_services()) == 0
    assert len(mock_forward.mock_calls) == 3

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        assert await hue_bridge.async_reset()

    assert len(mock_forward.mock_calls) == 3
    assert len(hass.services.async_services()) == 0


async def test_handle_unauthorized(hass):
    """Test handling an unauthorized error on update."""
    entry = Mock(async_setup=AsyncMock())
    entry.data = {"host": "1.2.3.4", "username": "mock-username"}
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

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


GROUP_RESPONSE = {
    "group_1": {
        "name": "Group 1",
        "lights": ["1", "2"],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 254,
            "hue": 10000,
            "sat": 254,
            "effect": "none",
            "xy": [0.5, 0.5],
            "ct": 250,
            "alert": "select",
            "colormode": "ct",
        },
        "state": {"any_on": True, "all_on": False},
    }
}
SCENE_RESPONSE = {
    "scene_1": {
        "name": "Cozy dinner",
        "lights": ["1", "2"],
        "owner": "ffffffffe0341b1b376a2389376a2389",
        "recycle": True,
        "locked": False,
        "appdata": {"version": 1, "data": "myAppData"},
        "picture": "",
        "lastupdated": "2015-12-03T10:09:22",
        "version": 2,
    }
}


async def test_hue_activate_scene(hass, mock_api):
    """Test successful hue_activate_scene."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "mock-host", "username": "mock-username"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, config_entry)

    mock_api.mock_group_responses.append(GROUP_RESPONSE)
    mock_api.mock_scene_responses.append(SCENE_RESPONSE)

    with patch("aiohue.Bridge", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.api is mock_api

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner"}
    with patch("aiohue.Bridge", return_value=mock_api):
        assert await hue_bridge.hue_activate_scene(call.data) is None

    assert len(mock_api.mock_requests) == 3
    assert mock_api.mock_requests[2]["json"]["scene"] == "scene_1"
    assert "transitiontime" not in mock_api.mock_requests[2]["json"]
    assert mock_api.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_transition(hass, mock_api):
    """Test successful hue_activate_scene with transition."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "mock-host", "username": "mock-username"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, config_entry)

    mock_api.mock_group_responses.append(GROUP_RESPONSE)
    mock_api.mock_scene_responses.append(SCENE_RESPONSE)

    with patch("aiohue.Bridge", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.api is mock_api

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner", "transition": 30}
    with patch("aiohue.Bridge", return_value=mock_api):
        assert await hue_bridge.hue_activate_scene(call.data) is None

    assert len(mock_api.mock_requests) == 3
    assert mock_api.mock_requests[2]["json"]["scene"] == "scene_1"
    assert mock_api.mock_requests[2]["json"]["transitiontime"] == 30
    assert mock_api.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_group_not_found(hass, mock_api):
    """Test failed hue_activate_scene due to missing group."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "mock-host", "username": "mock-username"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, config_entry)

    mock_api.mock_group_responses.append({})
    mock_api.mock_scene_responses.append(SCENE_RESPONSE)

    with patch("aiohue.Bridge", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.api is mock_api

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner"}
    with patch("aiohue.Bridge", return_value=mock_api):
        assert await hue_bridge.hue_activate_scene(call.data) is False


async def test_hue_activate_scene_scene_not_found(hass, mock_api):
    """Test failed hue_activate_scene due to missing scene."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "mock-host", "username": "mock-username"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, config_entry)

    mock_api.mock_group_responses.append(GROUP_RESPONSE)
    mock_api.mock_scene_responses.append({})

    with patch("aiohue.Bridge", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await hue_bridge.async_setup() is True

    assert hue_bridge.api is mock_api

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner"}
    with patch("aiohue.Bridge", return_value=mock_api):
        assert await hue_bridge.hue_activate_scene(call.data) is False
