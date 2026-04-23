"""Tests for the UniFi Access event platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api.models.websocket import (
    DeviceUpdate,
    DeviceUpdateData,
    DeviceUpdateDoor,
    HwDoorbell,
    HwDoorbellData,
    InsightsAdd,
    InsightsAddData,
    InsightsMetadata,
    InsightsMetadataEntry,
    LogActor,
    LogAdd,
    LogAddData,
    LogAuthentication,
    LogEvent,
    LogSource,
    LogTarget,
    RemoteView,
    RemoteViewData,
    V2DeviceLocationState,
    V2DeviceUpdate,
    V2DeviceUpdateData,
    V2LocationUpdate,
    V2LocationUpdateData,
    WebsocketMessage,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FRONT_DOOR_DOORBELL_ENTITY = "event.front_door_doorbell"
FRONT_DOOR_ACCESS_ENTITY = "event.front_door_access"
BACK_DOOR_DOORBELL_ENTITY = "event.back_door_doorbell"
BACK_DOOR_ACCESS_ENTITY = "event.back_door_access"


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


@pytest.fixture(autouse=True)
def only_event_platform() -> Generator[None]:
    """Limit setup to the event platform for event tests."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.EVENT]):
        yield


async def test_event_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event entities are created with expected state."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_doorbell_ring_event(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test doorbell ring event is fired when WebSocket message arrives."""
    handlers = _get_ws_handlers(mock_client)

    doorbell_msg = HwDoorbell(
        event="access.hw.door_bell",
        data=HwDoorbellData(
            door_id="door-001",
            door_name="Front Door",
            request_id="req-123",
        ),
    )

    await handlers["access.hw.door_bell"](doorbell_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "ring"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_doorbell_ring_event_wrong_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test doorbell ring event for unknown door is ignored."""
    handlers = _get_ws_handlers(mock_client)

    doorbell_msg = HwDoorbell(
        event="access.hw.door_bell",
        data=HwDoorbellData(
            door_id="door-unknown",
            door_name="Unknown Door",
            request_id="req-999",
        ),
    )

    await handlers["access.hw.door_bell"](doorbell_msg)
    await hass.async_block_till_done()

    # Front door entity should still have no event
    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    (
        "result",
        "expected_event_type",
        "door_id",
        "entity_id",
        "actor",
        "authentication",
    ),
    [
        (
            "ACCESS",
            "access_granted",
            "door-001",
            FRONT_DOOR_ACCESS_ENTITY,
            "John Doe",
            "NFC",
        ),
        (
            "BLOCKED",
            "access_denied",
            "door-002",
            BACK_DOOR_ACCESS_ENTITY,
            "Unknown",
            "PIN_CODE",
        ),
    ],
)
@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_access_event(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    result: str,
    expected_event_type: str,
    door_id: str,
    entity_id: str,
    actor: str,
    authentication: str,
) -> None:
    """Test access event is fired with correct mapping from API result."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData.model_construct(
            event_type="access.door.unlock",
            result=result,
            metadata=InsightsMetadata(
                door=[
                    InsightsMetadataEntry(
                        id=door_id,
                        display_name="Door",
                    )
                ],
                actor=InsightsMetadataEntry(
                    display_name=actor,
                ),
                authentication=InsightsMetadataEntry(
                    display_name=authentication,
                ),
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["event_type"] == expected_event_type
    assert state.attributes["actor"] == actor
    assert state.attributes["authentication"] == authentication
    assert state.attributes["result"] == result
    assert "direction" not in state.attributes
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_access_event_minimal_metadata(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access events work with minimal metadata (no actor or authentication)."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData.model_construct(
            event_type="access.door.unlock",
            result="ACCESS",
            metadata=InsightsMetadata.model_construct(
                door=[
                    InsightsMetadataEntry(
                        id="door-001",
                        display_name="Front Door",
                    )
                ],
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.attributes["result"] == "ACCESS"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_insights_no_door_id_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test insights event without door_id is ignored."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData.model_construct(
            event_type="access.door.unlock",
            result="ACCESS",
            metadata=InsightsMetadata(
                door=[InsightsMetadataEntry(id="", display_name="")],
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("result", "expected_event_type", "expected_result_attr"),
    [
        ("ACCESS", "access_granted", "ACCESS"),
        ("BLOCKED", "access_denied", "BLOCKED"),
        ("TIMEOUT", "access_denied", "TIMEOUT"),
        ("", "access_denied", None),
    ],
)
@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_access_event_result_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    result: str,
    expected_event_type: str,
    expected_result_attr: str | None,
) -> None:
    """Test result-to-event-type mapping with minimal attributes."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData.model_construct(
            event_type="access.door.unlock",
            result=result,
            metadata=InsightsMetadata(
                door=[
                    InsightsMetadataEntry(
                        id="door-001",
                        display_name="Front Door",
                    )
                ],
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == expected_event_type
    assert "actor" not in state.attributes
    assert "authentication" not in state.attributes
    assert state.attributes.get("result") == expected_result_attr
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_insights_empty_door_list_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test insights event with empty door list is ignored."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData(
            event_type="access.door.unlock",
            result="ACCESS",
            metadata=InsightsMetadata(door=[]),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_insights_multiple_doors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test insights event with multiple doors dispatches events for each."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData(
            event_type="access.door.unlock",
            result="ACCESS",
            metadata=InsightsMetadata(
                door=[
                    InsightsMetadataEntry(id="door-001", display_name="Front Door"),
                    InsightsMetadataEntry(id="door-002", display_name="Back Door"),
                ],
                actor=InsightsMetadataEntry(display_name="John Doe"),
                authentication=InsightsMetadataEntry(display_name="NFC"),
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    front_state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert front_state is not None
    assert front_state.attributes["event_type"] == "access_granted"
    assert front_state.attributes["actor"] == "John Doe"
    assert front_state.state == "2025-01-01T00:00:00.000+00:00"

    back_state = hass.states.get(BACK_DOOR_ACCESS_ENTITY)
    assert back_state is not None
    assert back_state.attributes["event_type"] == "access_granted"
    assert back_state.attributes["actor"] == "John Doe"
    assert back_state.state == "2025-01-01T00:00:00.000+00:00"


async def test_unload_entry_removes_listeners(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that events are not processed after config entry is unloaded."""
    handlers = _get_ws_handlers(mock_client)

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    doorbell_msg = HwDoorbell(
        event="access.hw.door_bell",
        data=HwDoorbellData(
            door_id="door-001",
            door_name="Front Door",
            request_id="req-after-unload",
        ),
    )

    await handlers["access.hw.door_bell"](doorbell_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unavailable"


async def _populate_device_mapping(
    handlers: dict[str, Callable[[WebsocketMessage], Awaitable[None]]],
) -> None:
    """Send a V2 location update to populate the device-to-door mapping."""
    location_msg = V2LocationUpdate(
        event="access.data.v2.location.update",
        data=V2LocationUpdateData(
            id="door-001",
            location_type="door",
            name="Front Door",
            device_ids=["hub-device-001", "camera-device-001"],
        ),
    )
    await handlers["access.data.v2.location.update"](location_msg)


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_access_granted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event dispatches access_granted."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                actor=LogActor(display_name="John Doe"),
                event=LogEvent(result="ACCESS"),
                authentication=LogAuthentication(credential_provider="NFC"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.attributes["actor"] == "John Doe"
    assert state.attributes["authentication"] == "NFC"
    assert state.attributes["result"] == "ACCESS"
    assert "direction" not in state.attributes
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_access_denied(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event dispatches access_denied for non-ACCESS result."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                event=LogEvent(result="BLOCKED"),
                authentication=LogAuthentication(credential_provider="PIN_CODE"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_denied"
    assert state.attributes["result"] == "BLOCKED"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_logs_add_unknown_device_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event with unknown device ID is ignored."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="unknown-device",
                        display_name="Unknown Hub",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


async def test_logs_add_without_location_update_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event is ignored when no device mapping exists."""
    handlers = _get_ws_handlers(mock_client)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_empty_result_dispatches_access_denied(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event with empty result dispatches access_denied."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                event=LogEvent(result=""),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_denied"
    assert "result" not in state.attributes
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_logs_add_no_device_config_target_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event without device_config target is ignored."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        door_id="door-001",  # enriched door_id must not bypass missing device_config
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="user",
                        id="some-user-id",
                        display_name="Some User",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


async def test_logs_add_empty_targets_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.logs.add event with empty targets list is ignored."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_stale_device_mapping_cleared(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test stale device mappings are cleared when a door's devices change."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    # Reassign door-001 to only have camera-device-001 (hub-device-001 removed)
    reassign_msg = V2LocationUpdate(
        event="access.data.v2.location.update",
        data=V2LocationUpdateData(
            id="door-001",
            location_type="door",
            name="Front Door",
            device_ids=["camera-device-001"],
        ),
    )
    await handlers["access.data.v2.location.update"](reassign_msg)

    # hub-device-001 should no longer resolve to door-001
    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                actor=LogActor(display_name="John Doe"),
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"

    # camera-device-001 should still resolve to door-001
    camera_log = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="camera-device-001",
                        display_name="Camera",
                    ),
                ],
                actor=LogActor(display_name="Jane Doe"),
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](camera_log)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_device_mapping_pruned_on_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test device-to-door mappings are pruned when a door is removed on refresh."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    # Simulate door-001 being removed from the hub
    mock_client.get_doors.return_value = [
        door for door in mock_client.get_doors.return_value if door.id != "door-001"
    ]

    # Trigger refresh via WebSocket reconnect
    on_disconnect = mock_client.start_websocket.call_args[1]["on_disconnect"]
    on_connect = mock_client.start_websocket.call_args[1]["on_connect"]
    on_disconnect()
    await hass.async_block_till_done()
    on_connect()
    await hass.async_block_till_done()

    # hub-device-001 mapping should have been pruned;
    # sending a log event for it must not raise an error
    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                ],
                actor=LogActor(display_name="John Doe"),
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    # door-001 entity was removed when the door disappeared
    assert hass.states.get(FRONT_DOOR_ACCESS_ENTITY) is None


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_remote_view_doorbell_ring_by_device_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.remote_view fires doorbell ring when device_id is in the mapping."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="hub-device-001"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "ring"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_remote_view_doorbell_ring_by_door_name_fallback(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.remote_view falls back to door_name lookup when device_id is unmapped."""
    handlers = _get_ws_handlers(mock_client)

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="unknown-device", door_name="Front Door"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "ring"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_remote_view_unknown_device_and_door_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.remote_view is ignored when both device_id and door_name are unknown."""
    handlers = _get_ws_handlers(mock_client)

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="unknown-device", door_name="Unknown Door"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_remote_view_device_mapping_via_device_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.remote_view resolves device_id populated by access.data.device.update."""
    handlers = _get_ws_handlers(mock_client)

    device_update_msg = DeviceUpdate(
        event="access.data.device.update",
        data=DeviceUpdateData(
            unique_id="intercom-device-001",
            door=DeviceUpdateDoor(unique_id="door-001"),
        ),
    )
    await handlers["access.data.device.update"](device_update_msg)
    await hass.async_block_till_done()

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="intercom-device-001"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "ring"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_remote_view_device_mapping_via_v2_device_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.remote_view resolves device_id populated by access.data.v2.device.update."""
    handlers = _get_ws_handlers(mock_client)

    v2_device_update_msg = V2DeviceUpdate(
        event="access.data.v2.device.update",
        data=V2DeviceUpdateData(
            id="intercom-v2-001",
            location_states=[V2DeviceLocationState(location_id="door-001")],
        ),
    )
    await handlers["access.data.v2.device.update"](v2_device_update_msg)
    await hass.async_block_till_done()

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="intercom-v2-001"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "ring"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_v2_device_update_multiple_location_states_maps_to_first_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test device with multiple location_states maps to the first valid door only."""
    handlers = _get_ws_handlers(mock_client)

    # Device has two location_states; should be mapped to the first door (door-001).
    v2_device_update_msg = V2DeviceUpdate(
        event="access.data.v2.device.update",
        data=V2DeviceUpdateData(
            id="hub-multi-001",
            location_states=[
                V2DeviceLocationState(location_id="door-001"),
                V2DeviceLocationState(location_id="door-002"),
            ],
        ),
    )
    await handlers["access.data.v2.device.update"](v2_device_update_msg)
    await hass.async_block_till_done()

    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="hub-multi-001"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    # Should ring front door (door-001), not back door (door-002)
    front_state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert front_state is not None
    assert front_state.attributes["event_type"] == "ring"
    assert front_state.state == "2025-01-01T00:00:00.000+00:00"

    back_state = hass.states.get(BACK_DOOR_DOORBELL_ENTITY)
    assert back_state is not None
    assert back_state.state == "unknown"


async def test_device_update_without_door_does_not_map(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.data.device.update without a door does not populate the mapping."""
    handlers = _get_ws_handlers(mock_client)

    device_update_msg = DeviceUpdate(
        event="access.data.device.update",
        data=DeviceUpdateData(unique_id="orphan-device"),
    )
    await handlers["access.data.device.update"](device_update_msg)
    await hass.async_block_till_done()

    # Sending a remote_view for that device should not fire a doorbell event
    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id="orphan-device"),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unknown"


async def test_device_update_empty_unique_id_does_not_pollute_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.data.device.update with empty unique_id does not create mapping."""
    handlers = _get_ws_handlers(mock_client)

    device_update_msg = DeviceUpdate(
        event="access.data.device.update",
        data=DeviceUpdateData(
            unique_id="",
            door=DeviceUpdateDoor(unique_id="door-001"),
        ),
    )
    await handlers["access.data.device.update"](device_update_msg)
    await hass.async_block_till_done()

    # An empty device_id must not accidentally resolve via the empty-string key
    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id=""),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unknown"


async def test_v2_device_update_empty_id_does_not_pollute_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test access.data.v2.device.update with empty id does not create mapping."""
    handlers = _get_ws_handlers(mock_client)

    v2_device_update_msg = V2DeviceUpdate(
        event="access.data.v2.device.update",
        data=V2DeviceUpdateData(
            id="",
            location_states=[V2DeviceLocationState(location_id="door-001")],
        ),
    )
    await handlers["access.data.v2.device.update"](v2_device_update_msg)
    await hass.async_block_till_done()

    # The empty-string device id must not produce an entry in _device_to_door
    remote_view_msg = RemoteView(
        event="access.remote_view",
        data=RemoteViewData(device_id=""),
    )
    await handlers["access.remote_view"](remote_view_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_DOORBELL_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_uah_door_via_enriched_door_id(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test UAH-DOOR access event resolved via library-enriched door_id."""
    handlers = _get_ws_handlers(mock_client)

    # UAH-DOOR: device MAC is not in coordinator's _device_to_door,
    # but the library has enriched msg.door_id via its MAC→door map.
    log_msg = LogAdd(
        event="access.logs.add",
        door_id="door-001",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="uah-door-mac-aa:bb:cc:dd:ee:ff",
                        display_name="UAH Door Reader",
                    ),
                ],
                actor=LogActor(display_name="Jane Doe"),
                event=LogEvent(result="ACCESS"),
                authentication=LogAuthentication(credential_provider="NFC"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.attributes["actor"] == "Jane Doe"
    assert state.attributes["authentication"] == "NFC"
    assert state.attributes["result"] == "ACCESS"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_uah_door_access_denied(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test UAH-DOOR access_denied event resolved via library-enriched door_id."""
    handlers = _get_ws_handlers(mock_client)

    log_msg = LogAdd(
        event="access.logs.add",
        door_id="door-001",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="uah-door-mac-aa:bb:cc:dd:ee:ff",
                        display_name="UAH Door Reader",
                    ),
                ],
                event=LogEvent(result="BLOCKED"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_denied"
    assert state.attributes["result"] == "BLOCKED"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


async def test_logs_add_uah_door_unknown_door_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test UAH-DOOR event is ignored when door_id is not a known door."""
    handlers = _get_ws_handlers(mock_client)

    log_msg = LogAdd(
        event="access.logs.add",
        door_id="door-unknown",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="uah-door-mac-aa:bb:cc:dd:ee:ff",
                        display_name="UAH Door Reader",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


async def test_logs_add_no_device_and_no_enriched_door_id_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test logs.add event is ignored when neither device mapping nor door_id resolves."""
    handlers = _get_ws_handlers(mock_client)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="unknown-device",
                        display_name="Unknown",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_insights_add_direction(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test direction attribute is included in access event when present."""
    handlers = _get_ws_handlers(mock_client)

    insights_msg = InsightsAdd(
        event="access.logs.insights.add",
        data=InsightsAddData.model_construct(
            event_type="access.door.unlock",
            result="ACCESS",
            metadata=InsightsMetadata(
                door=[InsightsMetadataEntry(id="door-001", display_name="Front Door")],
                opened_direction=[InsightsMetadataEntry(display_name="entry")],
            ),
        ),
    )

    await handlers["access.logs.insights.add"](insights_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.attributes["direction"] == "entry"
    assert state.state == "2025-01-01T00:00:00.000+00:00"


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_logs_add_direction(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test direction attribute is included in access event from logs.add when present."""
    handlers = _get_ws_handlers(mock_client)
    await _populate_device_mapping(handlers)

    log_msg = LogAdd(
        event="access.logs.add",
        data=LogAddData(
            source=LogSource(
                target=[
                    LogTarget(
                        type="device_config",
                        id="hub-device-001",
                        display_name="UA Hub Door",
                    ),
                    LogTarget(
                        type="device_config",
                        id="door_entry_method",
                        display_name="entry",
                    ),
                ],
                event=LogEvent(result="ACCESS"),
            ),
        ),
    )

    await handlers["access.logs.add"](log_msg)
    await hass.async_block_till_done()

    state = hass.states.get(FRONT_DOOR_ACCESS_ENTITY)
    assert state is not None
    assert state.attributes["event_type"] == "access_granted"
    assert state.attributes["direction"] == "entry"
    assert state.state == "2025-01-01T00:00:00.000+00:00"
