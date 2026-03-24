"""Tests for the UniFi Access event platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api.models.websocket import (
    HwDoorbell,
    HwDoorbellData,
    InsightsAdd,
    InsightsAddData,
    InsightsMetadata,
    InsightsMetadataEntry,
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


async def test_event_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.EVENT]):
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
        data=InsightsAddData(
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
        data=InsightsAddData(
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
        data=InsightsAddData(
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
