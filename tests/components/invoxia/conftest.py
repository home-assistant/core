"""Fixtures for invoxia integration tests."""
import json

from gps_tracker.client.datatypes import Device, Tracker, TrackerData, TrackerStatus
import pytest

from tests.common import load_fixture


@pytest.fixture
def trackers() -> list[Tracker]:
    """Form dummy data mocking client.get_trackers method."""
    data = json.loads(load_fixture("invoxia/trackers.json"))
    trackers: list[Tracker] = []
    for item in data:
        device = Device.get(item)
        if isinstance(device, Tracker):
            trackers.append(device)
    return trackers


@pytest.fixture
def tracker_status() -> TrackerStatus:
    """Form dummy data mocking client.get_tracker_status method."""
    data = json.loads(load_fixture("invoxia/tracker_status.json"))
    return TrackerStatus(**data)


@pytest.fixture
def tracker_data() -> list[TrackerData]:
    """Form dummy data mocking client.get_locations method."""
    data = json.loads(load_fixture("invoxia/tracker_data.json"))
    return [TrackerData(**item) for item in data]
