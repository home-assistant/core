"""Tests for the qBittorrent sensor platform, including errored torrents."""

from homeassistant.components.qbittorrent.coordinator import QBittorrentDataCoordinator
from homeassistant.components.qbittorrent.sensor import (
    SENSOR_TYPE_ACTIVE_TORRENTS,
    SENSOR_TYPE_ALL_TORRENTS,
    SENSOR_TYPE_ERRORED_TORRENTS,
    SENSOR_TYPE_INACTIVE_TORRENTS,
    SENSOR_TYPE_PAUSED_TORRENTS,
    SENSOR_TYPES,
)


def make_coordinator_with_states(states: list[str]) -> QBittorrentDataCoordinator:
    """Return a mock coordinator with torrents in the given states."""

    class MockCoordinator:
        # Simulate: data["torrents"] is a dict of torrent dicts, each with a "state"
        data = {
            "torrents": {
                f"torrent_{i}": {"state": state} for i, state in enumerate(states)
            }
        }

    return MockCoordinator()


def test_errored_torrents_sensor_counts() -> None:
    """Test that errored_torrents sensor counts 'error' and 'missingFiles' states."""
    coordinator = make_coordinator_with_states(
        ["error", "missingFiles", "downloading", "error", "stoppedDL"]
    )
    errored_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_ERRORED_TORRENTS
    )
    assert errored_sensor.value_fn(coordinator) == 3


def test_errored_torrents_sensor_zero_when_none() -> None:
    """Test that errored_torrents sensor returns 0 when no errored torrents exist."""
    coordinator = make_coordinator_with_states(
        ["downloading", "stoppedDL", "stalledUP"]
    )
    errored_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_ERRORED_TORRENTS
    )
    assert errored_sensor.value_fn(coordinator) == 0


def test_multiple_sensors() -> None:
    """Test that multiple sensors return expected values."""
    coordinator = make_coordinator_with_states(
        ["downloading", "stoppedDL", "stalledUP", "error", "missingFiles"]
    )
    all_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_ALL_TORRENTS
    )
    assert all_sensor.value_fn(coordinator) == 5
    active_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_ACTIVE_TORRENTS
    )
    assert isinstance(active_sensor.value_fn(coordinator), int)
    assert active_sensor.value_fn(coordinator) == 1
    paused_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_PAUSED_TORRENTS
    )
    assert isinstance(paused_sensor.value_fn(coordinator), int)
    assert paused_sensor.value_fn(coordinator) == 1
    inactive_sensor = next(
        desc for desc in SENSOR_TYPES if desc.key == SENSOR_TYPE_INACTIVE_TORRENTS
    )
    assert isinstance(inactive_sensor.value_fn(coordinator), int)
    assert inactive_sensor.value_fn(coordinator) == 1
