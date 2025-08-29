"""Tests for utility functions in the MyNeomitis integration."""

from homeassistant.components.myneomitis.utils import (
    CtnType,
    Sensors,
    format_week_schedule,
    get_device_by_rfid,
    parents_to_dict,
    seconds_to_hhmm,
)


def test_seconds_to_hhmm() -> None:
    """Test the conversion of seconds to HH:MM format."""
    assert seconds_to_hhmm(0) == "00:00"
    assert seconds_to_hhmm(3600) == "01:00"
    assert seconds_to_hhmm(3661) == "01:01"
    assert seconds_to_hhmm(86399) == "23:59"


def test_format_week_schedule_normal() -> None:
    """Test formatting of a normal weekly schedule."""
    input_schedule = {
        "0": [
            {"begin": 0, "end": 3600, "value": 1},
            {"begin": 7200, "end": 10800, "value": 2},
        ]
    }
    result = format_week_schedule(input_schedule)
    assert result["Monday"] == "00:00 → 01:00 : comfort   \n02:00 → 03:00 : eco       "
    assert result["Tuesday"] == "No schedule"


def test_format_week_schedule_relais() -> None:
    """Test formatting of a weekly schedule with relais mode."""
    input_schedule = {
        "0": [
            {"begin": 0, "end": 1800, "value": 1},
            {"begin": 3600, "end": 5400, "value": 2},
        ]
    }
    result = format_week_schedule(input_schedule, isRelais=True)
    assert result["Monday"] == "00:00 → 00:30 : on        \n01:00 → 01:30 : off       "


def test_parents_to_dict() -> None:
    """Test the conversion of a parents string to a dictionary."""
    assert parents_to_dict("") == {}
    assert parents_to_dict("gateway1") == {"gateway": "gateway1"}
    assert parents_to_dict("gateway1,primary1") == {
        "gateway": "gateway1",
        "primary": "primary1",
    }


def test_get_device_by_rfid() -> None:
    """Test retrieving a device by its RFID."""
    devices = [{"_id": "1", "rfid": "A"}, {"_id": "2", "rfid": "B"}]
    assert get_device_by_rfid(devices, "B") == {"_id": "2", "rfid": "B"}
    assert get_device_by_rfid(devices, "Z") is None


def test_ctntype_to_binary() -> None:
    """Test conversion of CtnType values to binary strings."""
    assert CtnType.to_binary(CtnType.NONE) == "00"
    assert CtnType.to_binary(CtnType.FLOOR) == "01"
    assert CtnType.to_binary(CtnType.FLOW) == "10"
    assert CtnType.to_binary(CtnType.OUTSIDE) == "11"


def test_ctntype_get_label() -> None:
    """Test retrieving labels for CtnType values."""
    assert CtnType.get_label(0) == "NTC"
    assert CtnType.get_label(1) == "Floor"
    assert CtnType.get_label(2) == "Flow"
    assert CtnType.get_label(3) == "Outside"
    assert CtnType.get_label(99) == "NTC"


def test_sensors_from_number() -> None:
    """Test the creation of Sensors object from a binary number."""
    sensors = Sensors.from_number(0b010110)
    assert sensors.ctn0 == 2
    assert sensors.ctn1 == 1
    assert sensors.ctn2 == 1
