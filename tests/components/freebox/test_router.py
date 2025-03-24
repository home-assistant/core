"""Tests for the Freebox utility methods."""

import json
from unittest.mock import Mock

from freebox_api.exceptions import HttpRequestError
import pytest

from homeassistant.components.freebox.router import get_hosts_list_if_supported, is_json

from .const import DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE, DATA_WIFI_GET_GLOBAL_CONFIG


async def test_is_json() -> None:
    """Test is_json method."""

    # Valid JSON values
    assert is_json("{}")
    assert is_json('{ "simple":"json" }')
    assert is_json(json.dumps(DATA_WIFI_GET_GLOBAL_CONFIG))
    assert is_json(json.dumps(DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE))

    # Not valid JSON values
    assert not is_json(None)
    assert not is_json("")
    assert not is_json("XXX")
    assert not is_json("{XXX}")


async def test_get_hosts_list_if_supported(
    router: Mock,
) -> None:
    """In router mode, get_hosts_list is supported and list is filled."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(router())
    assert supports_hosts is True
    # List must not be empty; but it's content depends on how many unit tests are executed...
    assert fbx_devices
    assert "d633d0c8-958c-43cc-e807-d881b076924b" in str(fbx_devices)


async def test_get_hosts_list_if_supported_bridge(
    router_bridge_mode: Mock,
) -> None:
    """In bridge mode, get_hosts_list is NOT supported and list is empty."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(
        router_bridge_mode()
    )
    assert supports_hosts is False
    assert fbx_devices == []


async def test_get_hosts_list_if_supported_bridge_error(
    mock_router_bridge_mode_error: Mock,
) -> None:
    """Other exceptions must be propagated."""
    with pytest.raises(HttpRequestError):
        await get_hosts_list_if_supported(mock_router_bridge_mode_error())
