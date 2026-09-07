"""Tests for the Amcrest sensor platform."""

from amcrest import AmcrestError
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import _MockAmcrestAPI, setup_amcrest

_PTZ_PRESET = "sensor.amcrest_camera_ptz_preset"
_SD_USED = "sensor.amcrest_camera_sd_used"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_sensors_report_camera_values(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """Both sensors expose the values reported by the camera."""
    mock_api.ptz_presets_count = 7
    mock_api.storage_all = {
        "total": (128.0, "GB"),
        "used": (64.0, "GB"),
        "used_percent": 50.0,
    }

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_PTZ_PRESET).state == "7"
    sd_used = hass.states.get(_SD_USED)
    assert sd_used.state == "50.00"
    assert sd_used.attributes["Total"] == "128.00 GB"
    assert sd_used.attributes["Used"] == "64.00 GB"


@pytest.mark.parametrize(
    ("used_percent", "expected_state"),
    [
        pytest.param(33.3333, "33.33", id="rounds_to_two_places"),
        pytest.param(0, "0.00", id="zero"),
        pytest.param(100, "100.00", id="full"),
    ],
)
@pytest.mark.usefixtures("mock_event_monitor")
async def test_sdcard_used_percent_formatting(
    hass: HomeAssistant,
    mock_api: _MockAmcrestAPI,
    used_percent: float,
    expected_state: str,
) -> None:
    """The SD card sensor formats usage to two decimal places."""
    mock_api.storage_all = {
        "total": (100.0, "GB"),
        "used": (50.0, "GB"),
        "used_percent": used_percent,
    }

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_SD_USED).state == expected_state


@pytest.mark.usefixtures("mock_event_monitor")
async def test_sensors_unavailable_when_camera_is(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """Sensors report unavailable rather than a stale value when the camera is down."""
    mock_api.available = False

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_PTZ_PRESET).state == STATE_UNAVAILABLE
    assert hass.states.get(_SD_USED).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_event_monitor")
async def test_sensor_update_error_is_handled(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """An AmcrestError while polling leaves the sensor unknown instead of raising."""
    mock_api.set_error("ptz_presets_count", AmcrestError("timeout"))

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_PTZ_PRESET).state == STATE_UNKNOWN
    # The other sensor is unaffected by its neighbour's failure.
    assert hass.states.get(_SD_USED).state == "50.00"
