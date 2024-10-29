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

    if len(device_point.enum_values) > 0 and device_point.writable:
        return Platform.SELECT

    if (
        description
        and description.native_unit_of_measurement == "DM"
        or (device_point.raw["maxValue"] and device_point.raw["minValue"])
    ):
        if device_point.writable:
            return Platform.NUMBER
        return Platform.SENSOR

    return Platform.SENSOR


WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

PARAMETER_ID_TO_EXCLUDE_F730 = (
    "40940",
    "47007",
    "47015",
    "47020",
    "47021",
    "47022",
    "47023",
    "47024",
    "47025",
    "47026",
    "47027",
    "47028",
    "47032",
    "47050",
    "47051",
    "47206",
    "47209",
    "47271",
    "47272",
    "47273",
    "47274",
    "47375",
    "47376",
    "47538",
    "47539",
    "47635",
    "47669",
    "47703",
    "47737",
    "47771",
    "47772",
    "47805",
    "47806",
    "47839",
    "47840",
    "47907",
    "47941",
    "47975",
    "48009",
    "48042",
    "48072",
    "50113",
)

PARAMETER_ID_TO_INCLUDE_SMO20 = (
    "40940",
    "47011",
    "47015",
    "47028",
    "47032",
    "50004",
)


def skip_entity(model: str, device_point: DevicePoint) -> bool:
    """Check if entity should be skipped for this device model."""
    if model == "SMO 20":
        if (
            len(device_point.smart_home_categories) > 0
            or device_point.parameter_id in PARAMETER_ID_TO_INCLUDE_SMO20
        ):
            return False
        return True
    if "F730" in model:
        # Entity names containing weekdays are used for advanced scheduling in the
        # heat pump and should not be exposed in the integration
        if any(d in device_point.parameter_name.lower() for d in WEEKDAYS):
            return True
        if device_point.parameter_id in PARAMETER_ID_TO_EXCLUDE_F730:
            return True
    return False
