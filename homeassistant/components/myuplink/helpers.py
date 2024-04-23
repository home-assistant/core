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
        len(device_point.enum_values) == 2
        and device_point.enum_values[0]["value"] == "0"
        and device_point.enum_values[1]["value"] == "1"
    ):
        if device_point.writable:
            return Platform.SWITCH
        return Platform.BINARY_SENSOR

    if (
        description
        and description.native_unit_of_measurement == "DM"
        or (device_point.raw["maxValue"] and device_point.raw["minValue"])
    ):
        if device_point.writable:
            return Platform.NUMBER
        return Platform.SENSOR

    return Platform.SENSOR


def skip_entity(model: str, device_point: DevicePoint) -> bool:
    """Check if entity should be skipped for this device model."""
    if model == "SMO 20":
        if len(device_point.smart_home_categories) > 0 or device_point.parameter_id in (
            "40940",
            "47011",
            "47015",
            "47028",
            "47032",
            "50004",
        ):
            return False
        return True
    return False
