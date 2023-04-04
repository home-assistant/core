"""Test Hue bridge."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import client_exceptions
from aiohue.errors import Unauthorized
from aiohue.v1 import HueBridgeV1
from aiohue.v2 import HueBridgeV2
import pytest

from homeassistant.components.hue import bridge
from homeassistant.components.hue.const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


async def test_bridge_setup_v1(hass: HomeAssistant, mock_api_v1) -> None:
    """Test a successful setup for V1 bridge."""
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


async def test_bridge_setup_v2(hass: HomeAssistant, mock_api_v2) -> None:
    """Test a successful setup for V2 bridge."""
    config_entry = Mock()
    config_entry.data = {"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 2}

    with patch.object(bridge, "HueBridgeV2", return_value=mock_api_v2), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v2
    assert isinstance(hue_bridge.api, HueBridgeV2)
    assert hue_bridge.api_version == 2
    assert len(mock_forward.mock_calls) == 5
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    assert forward_entries == {"light", "binary_sensor", "sensor", "switch", "scene"}


async def test_bridge_setup_invalid_api_key(hass: HomeAssistant) -> None:
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


async def test_bridge_setup_timeout(hass: HomeAssistant) -> None:
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


async def test_reset_unloads_entry_if_setup(hass: HomeAssistant, mock_api_v1) -> None:
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


async def test_handle_unauthorized(hass: HomeAssistant, mock_api_v1) -> None:
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
