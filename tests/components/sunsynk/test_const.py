"""Tests for const module."""

from custom_components.sunsynk.const import VALID_TIME_SLOTS


def test_valid_time_slots_count() -> None:
    """48 slots: 24 hours * 2 (on the hour + half hour)."""
    assert len(VALID_TIME_SLOTS) == 48


def test_valid_time_slots_format() -> None:
    """Test that all time slots have valid HH:MM format."""
    for slot in VALID_TIME_SLOTS:
        h, m = slot.split(":")
        assert len(h) == 2
        assert len(m) == 2
        assert 0 <= int(h) <= 23
        assert int(m) in (0, 30)


def test_valid_time_slots_boundaries() -> None:
    """Test that time slots start at 00:00 and end at 23:30."""
    assert VALID_TIME_SLOTS[0] == "00:00"
    assert VALID_TIME_SLOTS[-1] == "23:30"
