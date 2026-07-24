"""Tests for the Amcrest sensor platform."""

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest import AmcrestDevice
from homeassistant.components.amcrest.sensor import SENSOR_TYPES, AmcrestSensor

from .conftest import CAMERA_NAME, _MockAmcrestAPI

_PTZ_DESCRIPTION = next(d for d in SENSOR_TYPES if d.key == "ptz_preset")
_SDCARD_DESCRIPTION = next(d for d in SENSOR_TYPES if d.key == "sdcard")


async def test_ptz_sensor_update(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """PTZ sensor native value reflects preset count from the camera."""
    mock_api.ptz_presets_count = 7
    sensor = AmcrestSensor(CAMERA_NAME, device, _PTZ_DESCRIPTION)
    await sensor.async_update()
    assert sensor.native_value == 7


async def test_sdcard_sensor_update(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """SD card sensor reports usage percentage and Total/Used attributes."""
    mock_api.storage_all = {
        "total": (128.0, "GB"),
        "used": (64.0, "GB"),
        "used_percent": 50.0,
    }
    sensor = AmcrestSensor(CAMERA_NAME, device, _SDCARD_DESCRIPTION)
    await sensor.async_update()
    assert sensor.native_value == "50.00"
    assert sensor.extra_state_attributes["Total"] == "128.00 GB"
    assert sensor.extra_state_attributes["Used"] == "64.00 GB"


async def test_sensor_update_skips_when_unavailable(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """async_update leaves native_value None when the camera is unavailable."""
    mock_api.available = False
    sensor = AmcrestSensor(CAMERA_NAME, device, _PTZ_DESCRIPTION)
    await sensor.async_update()
    assert sensor.native_value is None


async def test_sensor_update_handles_error(
    mock_api: _MockAmcrestAPI, device: AmcrestDevice
) -> None:
    """AmcrestError during update is caught and does not propagate."""
    mock_api.set_error("ptz_presets_count", AmcrestError("timeout"))
    sensor = AmcrestSensor(CAMERA_NAME, device, _PTZ_DESCRIPTION)
    await sensor.async_update()  # must not raise


@pytest.mark.parametrize(
    ("used_percent", "expected_native_value"),
    [
        pytest.param(33.3333, "33.33", id="float"),
        pytest.param("N/A", "N/A", id="non_numeric"),
    ],
)
async def test_sdcard_sensor_used_percent_formatting(
    mock_api: _MockAmcrestAPI,
    device: AmcrestDevice,
    used_percent: float | str,
    expected_native_value: str,
) -> None:
    """SD card sensor handles both numeric and non-numeric used_percent values."""
    mock_api.storage_all = {
        "total": (100.0, "GB"),
        "used": (50.0, "GB"),
        "used_percent": used_percent,
    }
    sensor = AmcrestSensor(CAMERA_NAME, device, _SDCARD_DESCRIPTION)
    await sensor.async_update()
    assert sensor.native_value == expected_native_value
