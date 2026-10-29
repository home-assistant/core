"""Helper collection for myuplink."""

from myuplink import DevicePoint

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform

from .const import F_SERIES


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

    if (description and description.native_unit_of_measurement == "DM") or (
        device_point.raw["maxValue"] and device_point.raw["minValue"]
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
    "43001",
    "44259",
    "44331",
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
    "47043",
    "47044",
    "47045",
    "47046",
    "47047",
    "47048",
    "47049",
    "47050",
    "47051",
    "47206",
    "47209",
    "47261",
    "47262",
    "47263",
    "47264",
    "47266",
    "47267",
    "47268",
    "47269",
    "47270",
    "47271",
    "47272",
    "47273",
    "47274",
    "47275",
    "47277",
    "47278",
    "47279",
    "47280",
    "47281",
    "47282",
    "47283",
    "47284",
    "47285",
    "47286",
    "47287",
    "47288",
    "47289",
    "47290",
    "47347",
    "47348",
    "47374",
    "47375",
    "47376",
    "47378",
    "47379",
    "47416",
    "47526",
    "47537",
    "47538",
    "47539",
    "47544",
    "47545",
    "47550",
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
    "48072",
    "48181",
    "48185",
    "48200",
    "48210",
    "48275",
    "48364",
    "48391",
    "48392",
    "48393",
    "48394",
    "48395",
    "48396",
    "48397",
    "48398",
    "48442",
    "48442",
    "48452",
    "48460",
    "48461",
    "48462",
    "48463",
    "48464",
    "48465",
    "48466",
    "48467",
    "48568",
    "48642",
    "48643",
    "48644",
    "48645",
    "48659",
    "48660",
    "48711",
    "48712",
    "48713",
    "48714",
    "48715",
    "48716",
    "48717",
    "48718",
    "48740",
    "48741",
    "48742",
    "48743",
    "48826",
    "48891",
    "49190",
    "49227",
    "49563",
    "49564",
    "49567",
    "49568",
    "49569",
    "49570",
    "49571",
    "49572",
    "49573",
    "49574",
    "49580",
    "49584",
    "49728",
    "49740",
    "49741",
    "49742",
    "49743",
    "49744",
    "49745",
    "49746",
    "49747",
    "49797",
    "49874",
    "49909",
    "50113",
    "50249",
)

PARAMETER_ID_TO_INCLUDE_SMO20 = (
    "40013",
    "40033",
    "40940",
    "44069",
    "44071",
    "44073",
    "47011",
    "47015",
    "47028",
    "47032",
    "47398",
    "50004",
)


def skip_entity(model: str, device_point: DevicePoint) -> bool:
    """Check if entity should be skipped for this device model."""
    if device_point.parameter_id == "65535":
        # Garbage entity showing up on several firmware versions
        return True
    if model == "SMO 20":
        if (
            len(device_point.smart_home_categories) > 0
            or device_point.parameter_id in PARAMETER_ID_TO_INCLUDE_SMO20
        ):
            return False
        return True
    if model.lower().startswith("f"):
        # Entity names containing weekdays are used for advanced scheduling in the
        # heat pump and should not be exposed in the integration
        if any(d in device_point.parameter_name.lower() for d in WEEKDAYS):
            return True
        if device_point.parameter_id in PARAMETER_ID_TO_EXCLUDE_F730:
            return True
    if device_point.category.lower() in ["scheduling", "energy log"]:
        return True
    return False


def transform_model_series(prefix: str) -> str:
    """Remap all F-series models."""
    if prefix.lower().startswith("f"):
        return F_SERIES
    return prefix
