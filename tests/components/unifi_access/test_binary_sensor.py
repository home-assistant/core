"""Tests for the UniFi Access binary sensor platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion
from unifi_access_api import DoorPositionStatus
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateState,
    LocationUpdateV2,
    WebsocketMessage,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_ENTITY = "binary_sensor.front_door"
BACK_DOOR_ENTITY = "binary_sensor.back_door"


def _get_on_connect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_connect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_connect"]


def _get_on_disconnect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_disconnect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_disconnect"]


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


async def test_binary_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor entities are created with expected state."""
    with patch(
        "homeassistant.components.unifi_access.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_states(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test binary sensor states reflect initial door status."""
    assert hass.states.get(FRONT_DOOR_ENTITY).state == "off"
    assert hass.states.get(BACK_DOOR_ENTITY).state == "on"


async def test_binary_sensor_state_updates(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location updates change the binary sensor state."""
    handlers = _get_ws_handlers(mock_client)

    update_msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState(dps=DoorPositionStatus.OPEN),
        ),
    )

    await handlers["access.data.device.location_update_v2"](update_msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_ENTITY).state == "on"


async def test_ws_disconnect_marks_binary_sensors_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket disconnect marks binary sensors unavailable."""
    on_disconnect = _get_on_disconnect(mock_client)
    on_disconnect()
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unavailable"
    assert hass.states.get(BACK_DOOR_ENTITY).state == "unavailable"


async def test_ws_reconnect_restores_binary_sensor_states(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket reconnect restores binary sensor availability."""
    on_disconnect = _get_on_disconnect(mock_client)
    on_connect = _get_on_connect(mock_client)

    on_disconnect()
    await hass.async_block_till_done()
    assert hass.states.get(FRONT_DOOR_ENTITY).state == "unavailable"

    on_connect()
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_ENTITY).state == "off"
    assert hass.states.get(BACK_DOOR_ENTITY).state == "on"
