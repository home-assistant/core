"""Tests for System Bridge actions."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl

from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.services import (
    CONF_BRIDGE,
    CONF_KEY,
    CONF_TEXT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COMMAND, CONF_ID, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_UUID

from tests.common import AsyncMock, MockConfigEntry


@pytest.mark.parametrize(
    ("service", "service_data", "call_method", "call_args"),
    [
        (
            "open_path",
            {CONF_PATH: "/home/user/documents"},
            "open_path",
            [OpenPath(path="/home/user/documents")],
        ),
        (
            "open_url",
            {CONF_URL: "https://example.com"},
            "open_url",
            [OpenUrl(url="https://example.com")],
        ),
        (
            "power_command",
            {CONF_COMMAND: "shutdown"},
            "power_shutdown",
            [],
        ),
        (
            "send_keypress",
            {CONF_KEY: "backspace"},
            "keyboard_keypress",
            [KeyboardKey(key="backspace")],
        ),
        (
            "send_text",
            {CONF_TEXT: "Hello world"},
            "keyboard_text",
            [KeyboardText(text="Hello world")],
        ),
    ],
    ids=[
        "open_path",
        "open_url",
        "power_command_shutdown",
        "send_keypress",
        "send_text",
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    service: str,
    service_data: dict[str, Any],
    call_method: str,
    call_args: list[Any],
) -> None:
    """Test System Bridge service action calls."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    resp = await hass.services.async_call(
        DOMAIN,
        service,
        {
            CONF_BRIDGE: device_entry.id,
            **service_data,
        },
        blocking=True,
        return_response=True,
    )

    getattr(mock_websocket_client, call_method).assert_awaited_once_with(*call_args)
    assert resp == snapshot


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            "get_process_by_id",
            {CONF_ID: 1234},
        ),
        (
            "get_processes_by_name",
            {CONF_NAME: "name"},
        ),
    ],
    ids=["get_process_by_id", "get_processes_by_name"],
)
@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_get_process_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test System Bridge get process service action calls."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FIXTURE_UUID)}
    )
    assert device_entry

    resp = await hass.services.async_call(
        DOMAIN,
        service,
        {
            CONF_BRIDGE: device_entry.id,
            **service_data,
        },
        blocking=True,
        return_response=True,
    )

    assert resp == snapshot
