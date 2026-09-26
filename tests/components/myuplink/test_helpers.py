"""Tests for myUplink helpers."""

from myuplink import DevicePoint
import pytest

from homeassistant.components.myuplink.helpers import find_matching_platform
from homeassistant.const import Platform


@pytest.mark.parametrize(
    ("writable", "minimum", "maximum", "step", "unit", "expected_platform"),
    [
        pytest.param(True, 0, 1, 1, "", Platform.SWITCH, id="writable_boolean"),
        pytest.param(True, 0, 1, 1, "EB101", Platform.NUMBER, id="unit"),
        pytest.param(False, 0, 1, 1, "", Platform.SENSOR, id="read_only"),
        pytest.param(True, 0, 10, 1, "", Platform.NUMBER, id="numeric_range"),
        pytest.param(True, "", "", 1, "", Platform.SENSOR, id="invalid_range"),
    ],
)
def test_find_matching_platform(
    writable: bool,
    minimum: int | str,
    maximum: int | str,
    step: int,
    unit: str,
    expected_platform: Platform,
) -> None:
    """Test finding the matching platform for a device point."""
    device_point = DevicePoint(
        {
            "enumValues": [],
            "writable": writable,
            "minValue": minimum,
            "maxValue": maximum,
            "stepValue": step,
            "parameterUnit": unit,
        }
    )

    assert find_matching_platform(device_point) is expected_platform
