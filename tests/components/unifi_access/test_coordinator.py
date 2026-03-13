"""Tests for the UniFi Access coordinator."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FRONT_DOOR_ENTITY = "button.front_door_unlock"
BACK_DOOR_ENTITY = "button.back_door_unlock"


def _get_on_connect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_connect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_connect"]


def _get_on_disconnect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_disconnect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_disconnect"]


async def test_ws_disconnect_marks_entities_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket disconnect marks entities as unavailable."""
    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unknown"

    on_disconnect = _get_on_disconnect(mock_client)
    on_disconnect()
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unavailable"
    assert hass.states.get(BACK_DOOR_ENTITY).state == "unavailable"


async def test_ws_reconnect_restores_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket reconnect restores entity availability."""
    on_disconnect = _get_on_disconnect(mock_client)
    on_connect = _get_on_connect(mock_client)

    on_disconnect()
    await hass.async_block_till_done()
    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unavailable"

    on_connect()
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unknown"
    assert hass.states.get(BACK_DOOR_ENTITY).state == "unknown"


async def test_ws_connect_no_refresh_when_healthy(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket connect does not trigger redundant refresh when healthy."""
    on_connect = _get_on_connect(mock_client)

    on_connect()
    await hass.async_block_till_done()

    assert mock_client.get_doors.call_count == 1
