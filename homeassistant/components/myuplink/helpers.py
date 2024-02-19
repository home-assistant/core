"""Helper collection for myuplink."""

from myuplink import DevicePoint

from homeassistant.const import Platform


def find_matching_platform(device_point: DevicePoint) -> Platform:
    """Find entity platform for a DevicePoint."""
    if (
        len(device_point.enum_values) == 2
        and device_point.enum_values[0]["value"] == "0"
        and device_point.enum_values[1]["value"] == "1"
    ):
        if device_point.writable:
            # Change to Platform.SWITCH when platform is implemented
            # return Platform.SWITCH
            return Platform.SENSOR
        return Platform.BINARY_SENSOR

    return Platform.SENSOR
