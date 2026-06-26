"""Tests for the Amcrest binary sensor platform."""

from unittest.mock import MagicMock

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest import AmcrestDevice
from homeassistant.components.amcrest.binary_sensor import (
    BINARY_SENSORS,
    AmcrestBinarySensor,
)

from .conftest import CAMERA_NAME, SERIAL_NUMBER, _MockAmcrestAPI

_ONLINE = next(s for s in BINARY_SENSORS if s.key == "online")
_MOTION_POLLED = next(s for s in BINARY_SENSORS if s.key == "motion_detected_polled")
_MOTION_EVENT = next(s for s in BINARY_SENSORS if s.key == "motion_detected")


def test_binary_sensor_unique_id(device: AmcrestDevice) -> None:
    """Unique ID combines serial number, sensor key, and channel."""
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    assert sensor._attr_unique_id == f"{SERIAL_NUMBER}-motion_detected_polled-0"


def test_binary_sensor_no_unique_id_without_serial(mock_api: _MockAmcrestAPI) -> None:
    """No unique_id is assigned when the device has no serial number."""
    device = AmcrestDevice(
        api=mock_api,
        authentication=None,
        ffmpeg_arguments=["-pred", "1"],
        stream_source="snapshot",
        resolution=0,
        control_light=True,
        serial_number=None,
    )
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    assert sensor._attr_unique_id is None


def test_online_sensor_always_available(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """Online sensor reports available=True even when the API is unreachable."""
    mock_api.available = False
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _ONLINE)
    assert sensor.available is True


def test_non_online_sensor_follows_api_availability(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """Non-online sensors are unavailable when the camera API is unreachable."""
    mock_api.available = False
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    assert sensor.available is False


async def test_online_sensor_update(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """Online sensor is_on=True after update when the camera API is reachable."""
    mock_api.available = True
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _ONLINE)
    await sensor.async_update()
    assert sensor.is_on is True


@pytest.mark.parametrize(
    ("event_channels", "expected_is_on"),
    [
        pytest.param([1], True, id="motion_detected"),
        pytest.param([], False, id="no_motion"),
    ],
)
async def test_polled_binary_sensor_update(
    mock_api: _MockAmcrestAPI,
    device: AmcrestDevice,
    event_channels: list[int],
    expected_is_on: bool,
) -> None:
    """Polled binary sensor is_on reflects whether event channels fired."""
    mock_api.event_channels = event_channels
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    await sensor.async_update()
    assert sensor.is_on is expected_is_on


async def test_polled_binary_sensor_update_skips_when_unavailable(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """Polled binary sensor leaves is_on unchanged when camera is unavailable."""
    mock_api.available = False
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    initial_state = sensor.is_on
    await sensor.async_update()
    assert sensor.is_on is initial_state  # state unchanged


async def test_polled_binary_sensor_update_handles_error(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """AmcrestError during update is caught and does not propagate."""
    mock_api.set_error("event_channels_happened", AmcrestError("timeout"))
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_POLLED)
    await sensor.async_update()  # must not raise


def test_event_received_updates_state(device: AmcrestDevice) -> None:
    """async_event_received sets is_on from the dispatched event payload."""
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _MOTION_EVENT)
    sensor.async_write_ha_state = MagicMock()
    sensor.async_event_received(True)
    assert sensor.is_on is True
    sensor.async_event_received(False)
    assert sensor.is_on is False


def test_on_demand_update_online_mirrors_availability(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_on_demand_update_online sets is_on from current API availability."""
    sensor = AmcrestBinarySensor(CAMERA_NAME, device, _ONLINE)
    sensor.async_write_ha_state = MagicMock()

    mock_api.available = True
    sensor.async_on_demand_update_online()
    assert sensor.is_on is True

    mock_api.available = False
    sensor.async_on_demand_update_online()
    assert sensor.is_on is False
