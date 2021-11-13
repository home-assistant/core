"""Test Hue bridge."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import client_exceptions
from aiohue.errors import Unauthorized
from aiohue.v1 import HueBridgeV1
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import bridge
from homeassistant.components.hue.const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
)
from homeassistant.exceptions import ConfigEntryNotReady


async def test_bridge_setup(hass, mock_api_v1):
    """Test a successful setup."""
    config_entry = Mock()
    config_entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1}
    config_entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1
    assert isinstance(hue_bridge.api, HueBridgeV1)
    assert hue_bridge.api_version == 1
    assert len(mock_forward.mock_calls) == 3
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    assert forward_entries == {"light", "binary_sensor", "sensor"}


async def test_bridge_setup_invalid_api_key(hass):
    """Test we start config flow if username is no longer whitelisted."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1}
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

    with patch.object(
        hue_bridge.api, "initialize", side_effect=Unauthorized
    ), patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await hue_bridge.async_initialize_bridge() is False

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][2]["data"] == {"host": "1.2.3.4"}


async def test_bridge_setup_timeout(hass):
    """Test we retry to connect if we cannot connect."""
    entry = Mock()
    entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1}
    entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}
    hue_bridge = bridge.HueBridge(hass, entry)

    with patch.object(
        hue_bridge.api,
        "initialize",
        side_effect=client_exceptions.ServerDisconnectedError,
    ), pytest.raises(ConfigEntryNotReady):
        await hue_bridge.async_initialize_bridge()


async def test_reset_unloads_entry_if_setup(hass, mock_api_v1):
    """Test calling reset while the entry has been setup."""
    config_entry = Mock()
    config_entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1}
    config_entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    await asyncio.sleep(0)

    assert len(hass.services.async_services()) == 0
    assert len(mock_forward.mock_calls) == 3

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        assert await hue_bridge.async_reset()

    assert len(mock_forward.mock_calls) == 3
    assert len(hass.services.async_services()) == 0


async def test_handle_unauthorized(hass, mock_api_v1):
    """Test handling an unauthorized error on update."""
    config_entry = Mock(async_setup=AsyncMock())
    config_entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1}
    config_entry.options = {CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False}

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

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


async def test_hue_activate_scene(hass, mock_api_v1):
    """Test successful hue_activate_scene."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        "test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner"}
    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is True
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert "transitiontime" not in mock_api_v1.mock_requests[2]["json"]
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_transition(hass, mock_api_v1):
    """Test successful hue_activate_scene with transition."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        "test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch("aiohue.HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner", 30
            )
            is True
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert mock_api_v1.mock_requests[2]["json"]["transitiontime"] == 30
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_group_not_found(hass, mock_api_v1):
    """Test failed hue_activate_scene due to missing group."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        "test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append({})
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    call = Mock()
    call.data = {"group_name": "Group 1", "scene_name": "Cozy dinner"}
    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is False
        )


async def test_hue_activate_scene_scene_not_found(hass, mock_api_v1):
    """Test failed hue_activate_scene due to missing scene."""
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        "test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append({})

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch("aiohue.HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is False
        )
