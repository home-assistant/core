"""Tests for System Bridge actions."""

from typing import Any

import pytest
from pytest_homeassistant.common import AsyncMock, MockConfigEntry, MockUser
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
from systembridgeconnector.models.response import Response

from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.services import (
    CONF_BRIDGE,
    CONF_KEY,
    CONF_TEXT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COMMAND, CONF_ID, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_REQUEST_ID, FIXTURE_UUID


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

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
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


@pytest.mark.usefixtures("mock_version")
async def test_power_command_without_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a power command can be called without asking for a response."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
    )
    assert device_entry

    resp = await hass.services.async_call(
        DOMAIN,
        "power_command",
        {CONF_BRIDGE: device_entry.id, CONF_COMMAND: "shutdown"},
        blocking=True,
    )

    mock_websocket_client.power_shutdown.assert_awaited_once_with()
    assert resp is None


@pytest.mark.parametrize(
    ("service", "service_data", "call_method"),
    [
        ("open_path", {CONF_PATH: "/home/user/documents"}, "open_path"),
        ("open_url", {CONF_URL: "https://example.com"}, "open_url"),
        ("power_command", {CONF_COMMAND: "shutdown"}, "power_shutdown"),
        ("send_keypress", {CONF_KEY: "backspace"}, "keyboard_keypress"),
        ("send_text", {CONF_TEXT: "Hello world"}, "keyboard_text"),
    ],
)
@pytest.mark.usefixtures("mock_version")
async def test_service_error_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    service: str,
    service_data: dict[str, Any],
    call_method: str,
) -> None:
    """Test an error from the bridge raises instead of returning a payload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
    )
    assert device_entry

    getattr(mock_websocket_client, call_method).return_value = Response(
        id=FIXTURE_REQUEST_ID,
        type=EventType.ERROR,
        message="Something went wrong",
        data={},
    )

    with pytest.raises(
        HomeAssistantError, match=f"Failed to run {service}: Something went wrong"
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_BRIDGE: device_entry.id, **service_data},
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_version")
@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            ConnectionClosedException("Connection is closed"), id="connection_closed"
        ),
        pytest.param(ConnectionResetError("Connection reset"), id="connection_reset"),
    ],
)
async def test_service_connection_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    side_effect: Exception,
) -> None:
    """Test a closed or reset connection raises a connection error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
    )
    assert device_entry

    mock_websocket_client.power_shutdown.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match="A connection error occurred"):
        await hass.services.async_call(
            DOMAIN,
            "power_command",
            {CONF_BRIDGE: device_entry.id, CONF_COMMAND: "shutdown"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        ("open_path", {CONF_PATH: "/home/user/documents"}),
        ("open_url", {CONF_URL: "https://example.com"}),
        ("power_command", {CONF_COMMAND: "shutdown"}),
        ("send_keypress", {CONF_KEY: "backspace"}),
        ("send_text", {CONF_TEXT: "Hello world"}),
    ],
)
@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_admin_services_require_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test actions that control the host need an admin user."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
    )
    assert device_entry

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_BRIDGE: device_entry.id, **service_data},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )


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

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, FIXTURE_UUID), mock_config_entry.entry_id
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
