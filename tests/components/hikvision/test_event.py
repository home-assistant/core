"""Test Hikvision events."""

from collections.abc import Callable
from unittest.mock import MagicMock

from pyhik.constants import SENSOR_MAP
import pytest

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    EventDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID

from tests.common import MockConfigEntry

MOTION_ENTITY_ID = "event.front_camera_motion"
LINE_CROSSING_ENTITY_ID = "event.front_camera_line_crossing"
MOTION_CALLBACK_ID = f"{TEST_DEVICE_ID}.{SENSOR_MAP['vmd']}.1"
TEST_TRIP_TIME = "2024-01-01T12:00:00Z"


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.EVENT]


def get_callbacks(mock_hikcamera: MagicMock) -> dict[str, Callable[[str], None]]:
    """Return the update callbacks pyhik was handed, keyed by their ID."""
    return {
        call.args[1]: call.args[0]
        for call in mock_hikcamera.return_value.add_update_callback.call_args_list
    }


def set_event_state(
    mock_hikcamera: MagicMock, is_on: bool, detection_target: str | None
) -> None:
    """Set the attribute tuple pyhik reports for the event."""
    mock_hikcamera.return_value.fetch_attributes.return_value = (
        is_on,
        1,
        1,
        TEST_TRIP_TIME,
        detection_target,
    )


async def test_events_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test an event entity is created for each smart event."""
    await setup_integration(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids(Platform.EVENT)) == {
        MOTION_ENTITY_ID,
        LINE_CROSSING_ENTITY_ID,
    }

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == EventDeviceClass.MOTION
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "triggered",
        "human",
        "pet",
        "vehicle",
    ]


async def test_events_not_created_for_non_smart_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test events that never carry a detection target get no event entity."""
    mock_hikcamera.return_value.current_event_states = {
        SENSOR_MAP["vmd"]: [(False, 1)],
        SENSOR_MAP["diskfull"]: [(False, 1)],
        SENSOR_MAP["tamperdetection"]: [(False, 1)],
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids(Platform.EVENT) == [MOTION_ENTITY_ID]


async def test_events_no_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup when the device reports no events."""
    mock_hikcamera.return_value.current_event_states = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids(Platform.EVENT) == []


@pytest.mark.parametrize(
    ("detection_target", "expected_event_type"),
    [
        pytest.param("human", "human", id="human"),
        pytest.param("vehicle", "vehicle", id="vehicle"),
        pytest.param("pet", "pet", id="pet"),
        pytest.param(None, "triggered", id="no_detection_target"),
        pytest.param("bicycle", "triggered", id="unrecognized_detection_target"),
    ],
)
async def test_event_triggered_with_detection_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    detection_target: str | None,
    expected_event_type: str,
) -> None:
    """Test the detection target is reported as the event type."""
    await setup_integration(hass, mock_config_entry)

    set_event_state(mock_hikcamera, True, detection_target)
    get_callbacks(mock_hikcamera)[MOTION_CALLBACK_ID]("motion detected")
    await hass.async_block_till_done()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type
    # The detection target is the event type, never an extra state attribute.
    assert "detection_target" not in state.attributes


async def test_unrecognized_detection_target_logs_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a detection target the integration does not know about is reported."""
    await setup_integration(hass, mock_config_entry)

    set_event_state(mock_hikcamera, True, "bicycle")
    get_callbacks(mock_hikcamera)[MOTION_CALLBACK_ID]("motion detected")
    await hass.async_block_till_done()

    assert "Unknown Hikvision detection target 'bicycle'" in caplog.text


async def test_event_only_triggered_on_a_new_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test updates while the event stays active do not trigger a new event."""
    await setup_integration(hass, mock_config_entry)
    callbacks = get_callbacks(mock_hikcamera)

    set_event_state(mock_hikcamera, True, "human")
    callbacks[MOTION_CALLBACK_ID]("motion detected")
    await hass.async_block_till_done()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "human"

    # pyhik keeps updating while the event is active; that is the same trip.
    set_event_state(mock_hikcamera, True, "vehicle")
    callbacks[MOTION_CALLBACK_ID]("motion detected")
    await hass.async_block_till_done()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "human"

    set_event_state(mock_hikcamera, False, None)
    callbacks[MOTION_CALLBACK_ID]("motion cleared")
    await hass.async_block_till_done()

    set_event_state(mock_hikcamera, True, "vehicle")
    callbacks[MOTION_CALLBACK_ID]("motion detected")
    await hass.async_block_till_done()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "vehicle"


async def test_event_active_at_setup_is_not_replayed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test an event already active when the entity is added does not fire."""
    set_event_state(mock_hikcamera, True, "human")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_event_unavailable_when_stream_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test events go unavailable when the event stream disconnects."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # pyhik notifies every registered callback when the stream drops
    mock_hikcamera.return_value.stream_connected = False
    get_callbacks(mock_hikcamera)[MOTION_CALLBACK_ID]("stream disconnected")
    await hass.async_block_till_done()

    state = hass.states.get(MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("amount_of_channels", [2])
async def test_event_duplicate_channels_deduplicated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test duplicate channel entries do not create colliding unique IDs."""
    mock_hikcamera.return_value.get_type = "NVR"
    mock_hikcamera.return_value.current_event_states = {
        SENSOR_MAP["linedetection"]: [
            (False, 1),
            (False, 1),
            (False, 1),
            (False, 2),
            (False, 2),
        ],
    }

    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_entity_ids(Platform.EVENT)) == 2

    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert unique_ids == {
        f"{TEST_DEVICE_ID}_{SENSOR_MAP['linedetection']}_1",
        f"{TEST_DEVICE_ID}_{SENSOR_MAP['linedetection']}_2",
    }
