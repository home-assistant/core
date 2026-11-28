"""Tests for myUplink helpers."""

from typing import Any

from myuplink import DevicePoint
import pytest

from homeassistant.components.myuplink.helpers import find_matching_platform
from homeassistant.const import Platform


def _device_point(**overrides: Any) -> DevicePoint:
    """Return a device point without enum values, as the API reports it."""
    return DevicePoint(
        {
            "parameterUnit": "",
            "enumValues": [],
            "writable": True,
            "minValue": None,
            "maxValue": None,
            "stepValue": 1.0,
        }
        | overrides
    )


@pytest.mark.parametrize(
    ("overrides", "expected_platform"),
    [
        pytest.param(
            {"minValue": 0.0, "maxValue": 1.0}, Platform.SWITCH, id="on_off_setting"
        ),
        pytest.param(
            {"minValue": 0.0, "maxValue": 1.0, "parameterUnit": "(EB101)"},
            Platform.NUMBER,
            id="on_off_range_with_unit",
        ),
        pytest.param(
            {"minValue": 0.0, "maxValue": 15.0}, Platform.NUMBER, id="range_from_zero"
        ),
        pytest.param(
            {"minValue": -100.0, "maxValue": 0.0}, Platform.NUMBER, id="range_to_zero"
        ),
        pytest.param(
            {"minValue": -10.0, "maxValue": 10.0}, Platform.NUMBER, id="range"
        ),
        pytest.param(
            {"minValue": 0.0, "maxValue": 1.0, "writable": False},
            Platform.SENSOR,
            id="read_only_range",
        ),
        pytest.param({}, Platform.SENSOR, id="no_range"),
        pytest.param(
            {"minValue": 2147483647.0, "maxValue": 0.0},
            Platform.SENSOR,
            id="reversed_range",
        ),
        pytest.param(
            {"minValue": 2.0, "maxValue": ""}, Platform.SENSOR, id="empty_limit"
        ),
    ],
)
def test_find_matching_platform(
    overrides: dict[str, Any], expected_platform: Platform
) -> None:
    """Test which platform a writable device point without enum values ends up on."""
    assert find_matching_platform(_device_point(**overrides)) is expected_platform
