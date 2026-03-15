"""Tests for the UniFi Access button platform."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_ENTITY = "button.front_door_unlock"
BACK_DOOR_ENTITY = "button.back_door_unlock"


def _get_on_connect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_connect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_connect"]


def _get_on_disconnect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_disconnect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_disconnect"]


async def test_button_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unlock_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test pressing the unlock button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.front_door_unlock"},
        blocking=True,
    )

    mock_client.unlock_door.assert_awaited_once_with("door-001")


async def test_unlock_door_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test pressing the unlock button raises on API error."""
    mock_client.unlock_door.side_effect = ApiError("unlock failed")

    with pytest.raises(HomeAssistantError, match="Failed to unlock the door"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.front_door_unlock"},
            blocking=True,
        )


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
