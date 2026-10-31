"""Constants for the Tridonic DALI integration."""

DOMAIN = "dali"

CONF_BUS_POWER = "bus_power"

# IEC 62386 control-gear device types the integration handles.
DEVICE_TYPE_LED = 6
SUPPORTED_GEAR_DEVICE_TYPES = (DEVICE_TYPE_LED,)

# Human-readable names for each control-gear device type. The IEC 62386 part
# specifying a device type DTn is part 2(01+n) (e.g. DT6 → IEC 62386-207).
GEAR_DEVICE_TYPE_NAMES: dict[int, str] = {
    DEVICE_TYPE_LED: "LED module",
}

# Registry-identifier infixes. Control gear and control devices have
# independent DALI short-address spaces, so the kind is encoded to keep a
# same-numbered gear and control device as distinct registry devices.
GEAR_ID_INFIX = "gear"
CONTROL_DEVICE_ID_INFIX = "controldevice"


def registry_identifier(entry_id: str, address: int, *, input_device: bool) -> str:
    """Return the device-registry identifier for a DALI gear or control device."""
    infix = CONTROL_DEVICE_ID_INFIX if input_device else GEAR_ID_INFIX
    return f"{entry_id}_{infix}_{address}"
