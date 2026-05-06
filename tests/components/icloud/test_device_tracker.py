"""Tests for the iCloud device tracker."""

from unittest.mock import MagicMock, patch

from homeassistant.components.icloud.device_tracker import (
    IcloudTrackerEntity,
    add_entities,
)


def _make_tracker(location: dict | None) -> IcloudTrackerEntity:
    """Create an IcloudTrackerEntity with a device whose location is set to location."""
    mock_device = MagicMock()
    mock_device.location = location
    mock_device.unique_id = "device1"
    mock_account = MagicMock()
    return IcloudTrackerEntity(mock_account, mock_device)


def test_location_accuracy_returns_zero_when_no_location() -> None:
    """Test location_accuracy returns 0 when device location is None."""
    entity = _make_tracker(None)
    assert entity.location_accuracy == 0


def test_latitude_returns_none_when_no_location() -> None:
    """Test latitude returns None when device location is None."""
    entity = _make_tracker(None)
    assert entity.latitude is None


def test_longitude_returns_none_when_no_location() -> None:
    """Test longitude returns None when device location is None."""
    entity = _make_tracker(None)
    assert entity.longitude is None


def test_location_accuracy_returns_value_when_location_present() -> None:
    """Test location_accuracy returns the value from the location dict."""
    entity = _make_tracker({"horizontalAccuracy": 25.0})
    assert entity.location_accuracy == 25.0


def test_latitude_returns_value_when_location_present() -> None:
    """Test latitude returns the value from the location dict."""
    entity = _make_tracker({"latitude": 60.1699})
    assert entity.latitude == 60.1699


def test_longitude_returns_value_when_location_present() -> None:
    """Test longitude returns the value from the location dict."""
    entity = _make_tracker({"longitude": 24.9384})
    assert entity.longitude == 24.9384


def test_add_entities_creates_entity_when_location_is_none() -> None:
    """Test add_entities creates a tracker entity even when device location is None.

    Before this fix, devices with location=None were skipped, so a device whose
    stale location was cleared would never appear in HA at all. Entities should
    be created immediately and show 'unknown' until a fresh fix arrives.
    """
    mock_device = MagicMock()
    mock_device.location = None
    mock_device.unique_id = "device1"

    mock_account = MagicMock()
    mock_account.devices = {"device1": mock_device}

    tracked: set[str] = set()
    added: list = []

    def mock_async_add(entities, _update_before_add):
        added.extend(entities)

    with patch(
        "homeassistant.components.icloud.device_tracker.IcloudTrackerEntity",
        return_value=MagicMock(),
    ):
        add_entities(mock_account, mock_async_add, tracked)

    assert "device1" in tracked
    assert len(added) == 1
