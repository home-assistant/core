"""Helper collection for myuplink."""

from myuplink import DevicePoint

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform


def find_matching_platform(
    device_point: DevicePoint,
    description: SensorEntityDescription | NumberEntityDescription | None = None,
) -> Platform:
    """Find entity platform for a DevicePoint."""
    if (
        len(device_point.enum_values_list) == 2
        and device_point.enum_values_list[0].value == "0"
        and device_point.enum_values_list[1].value == "1"
    ):
        if device_point.writable:
            return Platform.SWITCH
        return Platform.BINARY_SENSOR

    if (description and description.native_unit_of_measurement == "DM") or (
        device_point.max_value and device_point.min_value
    ):
        if device_point.writable:
            return Platform.NUMBER
        return Platform.SENSOR

    return Platform.SENSOR
