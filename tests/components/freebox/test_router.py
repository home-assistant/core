"""Tests for the Freebox utility methods."""

import json
from pathlib import Path
import socket
from unittest.mock import Mock

from freebox_api.exceptions import HttpRequestError
import pytest

from homeassistant.components.freebox.router import (
    get_hosts_list_if_supported,
    is_json,
    read_device_name_from_file,
)

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
    # We expect 4 devices from lan_get_hosts_list.json and 1 from lan_get_hosts_list_guest.json
    assert len(fbx_devices) == 5
    assert "d633d0c8-958c-43cc-e807-d881b076924b" in str(fbx_devices)
    assert "d633d0c8-958c-42cc-e807-d881b476924b" in str(fbx_devices)


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


async def test_read_device_name_from_file_success(tmp_path: Path) -> None:
    """Test reading device name from a valid token file."""
    token_file = tmp_path / "token.conf"
    data = {"device_name": "MyFreeboxDevice"}
    token_file.write_text(json.dumps(data), encoding="utf-8")

    assert read_device_name_from_file(token_file) == "MyFreeboxDevice"


async def test_read_device_name_from_file_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reading device name from a token file with invalid JSON."""
    token_file = tmp_path / "token.conf"
    token_file.write_text("not a json", encoding="utf-8")

    monkeypatch.setattr(socket, "gethostname", lambda: "fallback-host")

    assert read_device_name_from_file(token_file) == "fallback-host"


async def test_read_device_name_from_file_missing_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test reading device name from a token file missing the device_name key."""
    token_file = tmp_path / "token.conf"
    token_file.write_text(json.dumps({}), encoding="utf-8")

    monkeypatch.setattr(socket, "gethostname", lambda: "fallback-host-2")

    assert read_device_name_from_file(token_file) == "fallback-host-2"


async def test_read_device_name_from_file_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test reading device name when the token file does not exist."""
    token_file = tmp_path / "does_not_exist.conf"

    monkeypatch.setattr(socket, "gethostname", lambda: "no-file-host")

    assert read_device_name_from_file(token_file) == "no-file-host"
