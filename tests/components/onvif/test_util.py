"""Test ONVIF util functions."""

from homeassistant.components.onvif.models import Event
from homeassistant.components.onvif.util import build_event_entity_names

# Example device UID that would be used as prefix
TEST_DEVICE_UID = "aa:bb:cc:dd:ee:ff"


def test_build_event_entity_names_unique_names() -> None:
    """Test build_event_entity_names with unique event names."""
    events = [
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/Motion_00000_00000_00000",
            name="Cell Motion Detection",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/PeopleDetector/People_00000_00000_00000",
            name="Person Detection",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/MyRuleDetector/VehicleDetect_00000",
            name="Vehicle Detection",
            platform="binary_sensor",
        ),
    ]

    result = build_event_entity_names(events)

    assert result == {
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/Motion_00000_00000_00000": "Cell Motion Detection",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/PeopleDetector/People_00000_00000_00000": "Person Detection",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/MyRuleDetector/VehicleDetect_00000": "Vehicle Detection",
    }


def test_build_event_entity_names_duplicated() -> None:
    """Test with multiple motion detection zones (realistic camera scenario)."""
    # Realistic scenario: Camera with motion detection on multiple source tokens
    events = [
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00200",
            name="Motion Alarm",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00100",
            name="Motion Alarm",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00000",
            name="Motion Alarm",
            platform="binary_sensor",
        ),
    ]

    result = build_event_entity_names(events)

    # Should be sorted by UID (source tokens: 00000, 00100, 00200)
    assert result == {
        f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00000": "Motion Alarm 1",
        f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00100": "Motion Alarm 2",
        f"{TEST_DEVICE_UID}_tns1:VideoSource/MotionAlarm_00200": "Motion Alarm 3",
    }


def test_build_event_entity_names_mixed_events() -> None:
    """Test realistic mix of unique and duplicate event names."""
    events = [
        # Multiple person detection with different rules
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/People_00000_00000_00000",
            name="Person Detection",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/People_00000_00000_00100",
            name="Person Detection",
            platform="binary_sensor",
        ),
        # Unique tamper detection
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/Tamper_00000_00000_00000",
            name="Tamper Detection",
            platform="binary_sensor",
        ),
        # Multiple line crossings with different rules
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/LineCross_00000_00000_00000",
            name="Line Detector Crossed",
            platform="binary_sensor",
        ),
        Event(
            uid=f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/LineCross_00000_00000_00100",
            name="Line Detector Crossed",
            platform="binary_sensor",
        ),
    ]

    result = build_event_entity_names(events)

    assert result == {
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/People_00000_00000_00000": "Person Detection 1",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/People_00000_00000_00100": "Person Detection 2",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/Tamper_00000_00000_00000": "Tamper Detection",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/LineCross_00000_00000_00000": "Line Detector Crossed 1",
        f"{TEST_DEVICE_UID}_tns1:RuleEngine/CellMotionDetector/LineCross_00000_00000_00100": "Line Detector Crossed 2",
    }


def test_build_event_entity_names_empty() -> None:
    """Test build_event_entity_names with empty list."""
    assert build_event_entity_names([]) == {}
