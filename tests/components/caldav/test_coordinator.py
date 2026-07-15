"""Tests for the caldav coordinator helpers."""

from caldav.objects import Event

from homeassistant.components.caldav.coordinator import _get_vevent


def test_get_vevent_without_data() -> None:
    """Test a resource with no data is treated as having no VEVENT."""
    event = Event(client=None, url="0.ics", data=None, parent=None, id="0")
    assert _get_vevent(event) is None
