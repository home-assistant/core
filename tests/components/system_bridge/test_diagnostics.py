"""Tests for the System Bridge diagnostics."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from systembridgeconnector.exceptions import (
    BadRequestException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.diagnostics import Diagnostics

from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import mock_data_listener, setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics while the host is disconnected."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
    mock_websocket_client.get_diagnostics.assert_not_called()


@pytest.fixture
async def listening_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with a connection that stays open."""

    async def listen(
        callback: Callable[[str, Any], Awaitable[None]] | None = None,
        power_state_callback: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        await mock_data_listener(callback, power_state_callback=power_state_callback)
        await asyncio.Event().wait()

    mock_websocket_client.connected = True
    mock_websocket_client.listen.side_effect = listen
    assert await setup_integration(hass, mock_config_entry)
    return mock_config_entry


async def test_diagnostics_app_bundle(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    listening_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the app's diagnostics bundle is included, with error text redacted."""
    mock_websocket_client.get_diagnostics.return_value = Diagnostics(
        **await async_load_json_object_fixture(hass, "diagnostics.json", DOMAIN)
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, listening_integration
    )

    assert diagnostics["connection"]["listening"] is True
    assert diagnostics["app"] == snapshot


@pytest.mark.parametrize(
    ("exception", "missing_reason"),
    [
        pytest.param(
            ConnectionClosedException("Connection is closed"),
            "not_connected",
            id="connection_closed",
        ),
        pytest.param(
            ConnectionResetError("Cannot write to closing transport"),
            "not_connected",
            id="connection_reset",
        ),
        pytest.param(
            ConnectionErrorException("Timeout waiting for diagnostics response"),
            "timeout",
            id="timeout",
        ),
        pytest.param(
            BadRequestException("Method not found"),
            "not_supported",
            id="not_supported",
        ),
    ],
)
async def test_diagnostics_app_bundle_missing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    listening_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    exception: Exception,
    missing_reason: str,
) -> None:
    """Test diagnostics still download when the app can't give its bundle."""
    mock_websocket_client.get_diagnostics.side_effect = exception

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, listening_integration
    )

    assert diagnostics["app"] == {"bundle": None, "missing_reason": missing_reason}


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            ConnectionClosedException("Connection is closed"), id="connection_closed"
        ),
        pytest.param(
            ConnectionErrorException("Timeout waiting for diagnostics response"),
            id="response_lost",
        ),
    ],
)
async def test_diagnostics_connection_lost_during_request(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    listening_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
    exception: Exception,
) -> None:
    """Test the connection state is read after the app's bundle is requested."""
    listen_task = listening_integration.runtime_data.listen_task
    assert listen_task is not None

    async def get_diagnostics() -> None:
        mock_websocket_client.connected = False
        listen_task.cancel()
        with suppress(asyncio.CancelledError):
            await listen_task
        raise exception

    mock_websocket_client.get_diagnostics.side_effect = get_diagnostics

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, listening_integration
    )

    assert diagnostics["connection"]["websocket_connected"] is False
    assert diagnostics["connection"]["listening"] is False
    assert diagnostics["app"] == {"bundle": None, "missing_reason": "not_connected"}
