"""Test the UniFi Protect event platform."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from uiprotect.data import Camera, Event, EventType, ModelType, SmartDetectObjectType

from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_ID,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.components.unifiprotect.event import EVENT_DESCRIPTIONS
from homeassistant.const import ATTR_ATTRIBUTION, Platform
from homeassistant.core import Event as HAEvent, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    remove_entities,
)

# Short delay for testing
TEST_VEHICLE_EVENT_DELAY = 0.05


@pytest.fixture(autouse=True)
def short_vehicle_delay():
    """Use a short delay for vehicle event tests."""
    with patch(
        "homeassistant.components.unifiprotect.event.VEHICLE_EVENT_DELAY_SECONDS",
        TEST_VEHICLE_EVENT_DELAY,
    ):
        yield


async def test_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)


async def test_doorbell_ring(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell ring event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[0]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.model_copy()
    new_camera.last_ring_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    timestamp = state.state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=50,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.model_copy()
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    # Event is already seen and has end, should now be off
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp

    # Now send an event that has an end right away
    event = Event(
        model=ModelType.EVENT,
        id="new_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=80,
        smart_detect_types=[SmartDetectObjectType.PACKAGE],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.model_copy()
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp
    unsub()


async def test_doorbell_nfc_scanned(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell NFC scanned event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[1]
    )

    ulp_id = "ulp_id"
    test_user_full_name = "Test User"
    test_nfc_id = "test_nfc_id"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.NFC_CARD_SCANNED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"nfc": {"nfc_id": test_nfc_id, "user_id": "test_user_id"}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_nfc_card_scanned_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_keyring = Mock()
    mock_keyring.registry_id = test_nfc_id
    mock_keyring.registry_type = "nfc"
    mock_keyring.ulp_user = ulp_id
    ufp.api.bootstrap.keyrings.add(mock_keyring)

    mock_ulp_user = Mock()
    mock_ulp_user.ulp_id = ulp_id
    mock_ulp_user.full_name = test_user_full_name
    mock_ulp_user.status = "ACTIVE"
    ufp.api.bootstrap.ulp_users.add(mock_ulp_user)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["nfc_id"] == "test_nfc_id"
    assert state.attributes["full_name"] == test_user_full_name

    unsub()


async def test_doorbell_nfc_scanned_ulpusr_deactivated(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell NFC scanned event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[1]
    )

    ulp_id = "ulp_id"
    test_user_full_name = "Test User"
    test_nfc_id = "test_nfc_id"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.NFC_CARD_SCANNED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"nfc": {"nfc_id": test_nfc_id, "user_id": "test_user_id"}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_nfc_card_scanned_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_keyring = Mock()
    mock_keyring.registry_id = test_nfc_id
    mock_keyring.registry_type = "nfc"
    mock_keyring.ulp_user = ulp_id
    ufp.api.bootstrap.keyrings.add(mock_keyring)

    mock_ulp_user = Mock()
    mock_ulp_user.ulp_id = ulp_id
    mock_ulp_user.full_name = test_user_full_name
    mock_ulp_user.status = "DEACTIVATED"
    ufp.api.bootstrap.ulp_users.add(mock_ulp_user)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["nfc_id"] == "test_nfc_id"
    assert state.attributes["full_name"] == "Test User"
    assert state.attributes["user_status"] == "DEACTIVATED"

    unsub()


async def test_doorbell_nfc_scanned_no_ulpusr(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell NFC scanned event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[1]
    )

    ulp_id = "ulp_id"
    test_nfc_id = "test_nfc_id"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.NFC_CARD_SCANNED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"nfc": {"nfc_id": test_nfc_id, "user_id": "test_user_id"}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_nfc_card_scanned_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_keyring = Mock()
    mock_keyring.registry_id = test_nfc_id
    mock_keyring.registry_type = "nfc"
    mock_keyring.ulp_user = ulp_id
    ufp.api.bootstrap.keyrings.add(mock_keyring)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["nfc_id"] == "test_nfc_id"
    assert state.attributes["full_name"] == ""

    unsub()


async def test_doorbell_nfc_scanned_no_keyring(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell NFC scanned event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[1]
    )

    test_nfc_id = "test_nfc_id"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.NFC_CARD_SCANNED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"nfc": {"nfc_id": test_nfc_id, "user_id": "test_user_id"}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_nfc_card_scanned_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["nfc_id"] == "test_nfc_id"
    assert state.attributes["full_name"] == ""

    unsub()


async def test_doorbell_fingerprint_identified(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell fingerprint identified event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[2]
    )

    ulp_id = "ulp_id"
    test_user_full_name = "Test User"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.FINGERPRINT_IDENTIFIED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"fingerprint": {"ulp_id": ulp_id}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_fingerprint_identified_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_ulp_user = Mock()
    mock_ulp_user.ulp_id = ulp_id
    mock_ulp_user.full_name = test_user_full_name
    mock_ulp_user.status = "ACTIVE"
    ufp.api.bootstrap.ulp_users.add(mock_ulp_user)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["ulp_id"] == ulp_id
    assert state.attributes["full_name"] == test_user_full_name

    unsub()


async def test_doorbell_fingerprint_identified_user_deactivated(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell fingerprint identified event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[2]
    )

    ulp_id = "ulp_id"
    test_user_full_name = "Test User"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.FINGERPRINT_IDENTIFIED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"fingerprint": {"ulp_id": ulp_id}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_fingerprint_identified_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_ulp_user = Mock()
    mock_ulp_user.ulp_id = ulp_id
    mock_ulp_user.full_name = test_user_full_name
    mock_ulp_user.status = "DEACTIVATED"
    ufp.api.bootstrap.ulp_users.add(mock_ulp_user)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["ulp_id"] == ulp_id
    assert state.attributes["full_name"] == "Test User"
    assert state.attributes["user_status"] == "DEACTIVATED"

    unsub()


async def test_doorbell_fingerprint_identified_no_user(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell fingerprint identified event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[2]
    )

    ulp_id = "ulp_id"

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.FINGERPRINT_IDENTIFIED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"fingerprint": {"ulp_id": ulp_id}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_fingerprint_identified_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["ulp_id"] == ulp_id
    assert state.attributes["full_name"] == ""

    unsub()


async def test_doorbell_fingerprint_not_identified(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell fingerprint identified event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[2]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.FINGERPRINT_IDENTIFIED,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={"fingerprint": {}},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_fingerprint_identified_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert state.attributes["ulp_id"] == ""

    unsub()


async def test_vehicle_detection_basic(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test basic vehicle detection event with thumbnails."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with vehicle thumbnail
    event = Event(
        model=ModelType.EVENT,
        id="test_vehicle_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 95,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id",
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_vehicle_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received vehicle detection event
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_vehicle_event_id"
    assert state.attributes["confidence"] == 95
    assert "clock_best_wall" in state.attributes
    assert "license_plate" not in state.attributes

    unsub()


async def test_vehicle_detection_with_lpr_ufp6(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test vehicle detection with license plate recognition (UFP 6.0+ format)."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with vehicle thumbnail and LPR in group.matched_name (UFP 6.0+)
    event = Event(
        model=ModelType.EVENT,
        id="test_lpr_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 98,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id",
                    "group": {
                        "id": "lpr_group_1",
                        "matched_name": "ABC123",
                        "confidence": 95,
                    },
                    "attributes": {
                        "color": {"val": "blue", "confidence": 90},
                        "vehicle_type": {"val": "sedan", "confidence": 85},
                    },
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_lpr_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received vehicle detection event
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_lpr_event_id"
    assert state.attributes["confidence"] == 98
    assert state.attributes["license_plate"] == "ABC123"
    assert "attributes" in state.attributes
    assert state.attributes["attributes"]["color"]["val"] == "blue"
    assert state.attributes["attributes"]["vehicleType"]["val"] == "sedan"

    unsub()


async def test_vehicle_detection_with_lpr_legacy(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test vehicle detection with license plate recognition (legacy format)."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with vehicle thumbnail and LPR in name field (legacy)
    event = Event(
        model=ModelType.EVENT,
        id="test_lpr_legacy_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 92,
                    "clock_best_wall": fixed_now,
                    "name": "XYZ789",
                    "cropped_id": "test_thumb_id",
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_lpr_legacy_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received vehicle detection event
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_lpr_legacy_event_id"
    assert state.attributes["confidence"] == 92
    assert state.attributes["license_plate"] == "XYZ789"

    unsub()


async def test_vehicle_detection_multiple_thumbnails(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test vehicle detection with multiple thumbnails - should pick best LPR."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with multiple vehicle thumbnails - best should be highest confidence LPR
    event = Event(
        model=ModelType.EVENT,
        id="test_multi_thumbnail_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 70,
                    "clock_best_wall": fixed_now - timedelta(seconds=2),
                    "cropped_id": "test_thumb_id",
                },
                {
                    "type": "vehicle",
                    "confidence": 85,
                    "clock_best_wall": fixed_now - timedelta(seconds=1),
                    "cropped_id": "test_thumb_id_2",
                    "group": {
                        "id": "lpr_group_2",
                        "matched_name": "LOW_CONF",
                        "confidence": 85,
                    },
                },
                {
                    "type": "vehicle",
                    "confidence": 99,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id_3",
                    "group": {
                        "id": "lpr_group_3",
                        "matched_name": "BEST_LPR",
                        "confidence": 99,
                    },
                },
                {
                    "type": "person",  # Should be ignored
                    "confidence": 100,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id_person",
                },
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_multi_thumbnail_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received vehicle detection event with highest confidence LPR
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_multi_thumbnail_id"
    assert state.attributes["confidence"] == 99
    assert state.attributes["license_plate"] == "BEST_LPR"

    unsub()


async def test_vehicle_detection_no_thumbnails(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test vehicle detection event without thumbnails - should not fire."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event without detected_thumbnails
    event = Event(
        model=ModelType.EVENT,
        id="test_no_thumbnails_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={},
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_no_thumbnails_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer to expire
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should NOT have received any events (no vehicle thumbnails)
    assert len(events) == 0

    unsub()


async def test_vehicle_detection_timer_reset_on_new_thumbnail(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test that timer resets when new thumbnails arrive for same event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with one thumbnail
    event = Event(
        model=ModelType.EVENT,
        id="test_timer_reset_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 80,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id_1",
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_timer_reset_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    # Wait briefly (timer hasn't expired yet)
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY / 2)
    await hass.async_block_till_done()

    # No event yet (timer hasn't expired)
    assert len(events) == 0

    # Update with better thumbnail - should reset timer
    event.metadata = {
        "detected_thumbnails": [
            {
                "type": "vehicle",
                "confidence": 80,
                "clock_best_wall": fixed_now,
                "cropped_id": "test_thumb_id_1",
            },
            {
                "type": "vehicle",
                "confidence": 95,
                "clock_best_wall": fixed_now + timedelta(seconds=1),
                "cropped_id": "test_thumb_id_2",
                "group": {
                    "id": "lpr_group_4",
                    "matched_name": "BETTER_LPR",
                    "confidence": 95,
                },
            },
        ]
    }

    ufp.api.bootstrap.events = {event.id: event}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    # Still no event (timer extended)
    assert len(events) == 0

    # Wait for timer to expire
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Now should have the event with the better LPR
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes["confidence"] == 95
    assert state.attributes["license_plate"] == "BETTER_LPR"

    unsub()


async def test_vehicle_detection_new_event_cancels_timer(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test that new event cancels timer for previous event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create first event
    event1 = Event(
        model=ModelType.EVENT,
        id="test_event_1",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=5),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 80,
                    "clock_best_wall": fixed_now - timedelta(seconds=4),
                    "cropped_id": "test_thumb_id",
                    "group": {
                        "id": "lpr_group_5",
                        "matched_name": "FIRST",
                        "confidence": 80,
                    },
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_event_1"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event1.id: event1}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event1
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    # Wait briefly (timer hasn't expired yet)
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY / 2)
    await hass.async_block_till_done()

    # No event yet
    assert len(events) == 0

    # Send new event - should fire first event immediately
    event2 = Event(
        model=ModelType.EVENT,
        id="test_event_2",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 95,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id",
                    "group": {
                        "id": "lpr_group_6",
                        "matched_name": "SECOND",
                        "confidence": 95,
                    },
                }
            ]
        },
    )

    new_camera.last_smart_detect_event_id = "test_event_2"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event2.id: event2}

    mock_msg.new_obj = event2
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    # Wait for second event's timer
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have two events - first fired immediately when second arrived
    assert len(events) == 2
    # First event fired immediately when second event arrived
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_event_1"
    assert state.attributes["license_plate"] == "FIRST"
    # Second event fired after timer
    state = events[1].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_event_2"
    assert state.attributes["license_plate"] == "SECOND"

    unsub()


async def test_vehicle_detection_timer_cleanup_on_remove(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test that pending timer is cancelled when entity is removed."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    # Create event with vehicle thumbnail
    event = Event(
        model=ModelType.EVENT,
        id="test_cleanup_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 90,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_cleanup_thumb_id",
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_cleanup_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    # Timer is now pending - remove the entity before it fires
    await remove_entities(hass, ufp, [doorbell])
    await hass.async_block_till_done()

    # Wait past when timer would have fired
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Entity should be gone and no event should have fired
    state = hass.states.get(entity_id)
    assert state is None


async def test_vehicle_detection_refire_on_lpr_data(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test that event refires when LPR data arrives after initial detection."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with vehicle thumbnail but NO LPR data
    event = Event(
        model=ModelType.EVENT,
        id="test_refire_lpr_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 85,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id",
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_refire_lpr_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer to expire - first event should fire without LPR
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received first event without LPR
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_refire_lpr_id"
    assert state.attributes["confidence"] == 85
    assert "license_plate" not in state.attributes

    # Now LPR data arrives for the same event
    event.metadata = {
        "detected_thumbnails": [
            {
                "type": "vehicle",
                "confidence": 85,
                "clock_best_wall": fixed_now,
                "cropped_id": "test_thumb_id",
            },
            {
                "type": "vehicle",
                "confidence": 95,
                "clock_best_wall": fixed_now + timedelta(seconds=1),
                "cropped_id": "test_thumb_id_lpr",
                "group": {
                    "id": "lpr_group",
                    "matched_name": "ABC123",
                    "confidence": 95,
                },
            },
        ]
    }

    ufp.api.bootstrap.events = {event.id: event}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the new timer to expire
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received second event WITH LPR data
    assert len(events) == 2
    state = events[1].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_refire_lpr_id"
    assert state.attributes["confidence"] == 95
    assert state.attributes["license_plate"] == "ABC123"

    unsub()


async def test_vehicle_detection_no_refire_same_data(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test that event does NOT refire when same data arrives again."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 4, 4)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[3]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)

    # Create event with vehicle thumbnail
    event = Event(
        model=ModelType.EVENT,
        id="test_no_refire_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
        metadata={
            "detected_thumbnails": [
                {
                    "type": "vehicle",
                    "confidence": 90,
                    "clock_best_wall": fixed_now,
                    "cropped_id": "test_thumb_id",
                    "group": {
                        "id": "lpr_group",
                        "matched_name": "XYZ789",
                        "confidence": 90,
                    },
                }
            ]
        },
    )

    new_camera = doorbell.model_copy()
    new_camera.last_smart_detect_event_id = "test_no_refire_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    # Wait for the timer to expire
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should have received one event
    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_no_refire_id"
    assert state.attributes["license_plate"] == "XYZ789"

    # Send the same event again with identical data
    ufp.ws_msg(mock_msg)
    await asyncio.sleep(TEST_VEHICLE_EVENT_DELAY * 2)
    await hass.async_block_till_done()

    # Should NOT have received another event (same data)
    assert len(events) == 1

    unsub()
