"""Tests for the Place device shadow data models."""

from place.models.device_shadow import AlarmStatus, PlaceDeviceShadow

FULL_SHADOW = {
    "state": {
        "reported": {
            "deviceId": "device-001",
            "model": "MODEL-X",
            "fwPackageId": "fw-1.0",
            "autoUpdate": True,
            "secureBuild": True,
            "coAlarmStatus": 0,
            "heatAlarmStatus": 3,
            "smokeAlarmStatus": 5,
        }
    }
}


def test_from_shadow_full() -> None:
    """Test parsing a shadow payload."""
    shadow = PlaceDeviceShadow.from_shadow(FULL_SHADOW)

    # Alarm statuses
    assert shadow.co_alarm_status is AlarmStatus.IDLE
    assert shadow.heat_alarm_status is AlarmStatus.ALARM
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED


def test_from_shadow_without_state_wrapper() -> None:
    """Test parsing a flat reported dict (no state.reported wrapper)."""
    reported = {"coAlarmStatus": 3, "heatAlarmStatus": 0, "smokeAlarmStatus": 5}
    shadow = PlaceDeviceShadow.from_shadow(reported)

    assert shadow.co_alarm_status is AlarmStatus.ALARM
    assert shadow.heat_alarm_status is AlarmStatus.IDLE
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED


def test_from_shadow_empty() -> None:
    """Test parsing an empty shadow returns defaults."""
    shadow = PlaceDeviceShadow.from_shadow({})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT
    assert shadow.heat_alarm_status is AlarmStatus.NOT_PRESENT
    assert shadow.smoke_alarm_status is AlarmStatus.NOT_PRESENT


def test_from_shadow_invalid_alarm_value() -> None:
    """Test that out-of-range alarm values default to NOT_PRESENT."""
    shadow = PlaceDeviceShadow.from_shadow({"coAlarmStatus": 99})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT


def test_from_shadow_null_alarm_value() -> None:
    """Test that null alarm values default to NOT_PRESENT."""
    shadow = PlaceDeviceShadow.from_shadow({"coAlarmStatus": None})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT


def test_merge_sparse_update() -> None:
    """Test that a sparse update only changes provided fields."""
    shadow = PlaceDeviceShadow.from_shadow(FULL_SHADOW)

    assert shadow.co_alarm_status is AlarmStatus.IDLE

    shadow.merge({"state": {"reported": {"coAlarmStatus": 3}}})

    # Updated fields
    assert shadow.co_alarm_status is AlarmStatus.ALARM

    # Unchanged fields
    assert shadow.heat_alarm_status is AlarmStatus.ALARM
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED


def test_alarm_status_enum_values() -> None:
    """Test AlarmStatus enum has correct integer mappings."""
    assert AlarmStatus.IDLE == 0
    assert AlarmStatus.TEST == 1
    assert AlarmStatus.PRE_ALARM == 2
    assert AlarmStatus.ALARM == 3
    assert AlarmStatus.CRITICAL_ALARM == 4
    assert AlarmStatus.HUSHED == 5
    assert AlarmStatus.NOT_PRESENT == 6
