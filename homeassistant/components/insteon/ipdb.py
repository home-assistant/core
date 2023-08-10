"""Utility methods for the Insteon platform."""
from collections.abc import Iterable

from pyinsteon.device_types.device_base import Device
from pyinsteon.device_types.ipdb import (
    AccessControl_Morningstar,
    ClimateControl_Thermostat,
    ClimateControl_WirelessThermostat,
    DimmableLightingControl,
    DimmableLightingControl_Dial,
    DimmableLightingControl_DinRail,
    DimmableLightingControl_FanLinc,
    DimmableLightingControl_InLineLinc01,
    DimmableLightingControl_InLineLinc02,
    DimmableLightingControl_KeypadLinc_6,
    DimmableLightingControl_KeypadLinc_8,
    DimmableLightingControl_LampLinc,
    DimmableLightingControl_OutletLinc,
    DimmableLightingControl_SwitchLinc01,
    DimmableLightingControl_SwitchLinc02,
    DimmableLightingControl_ToggleLinc,
    EnergyManagement_LoadController,
    SecurityHealthSafety_DoorSensor,
    SecurityHealthSafety_LeakSensor,
    SecurityHealthSafety_MotionSensor,
    SecurityHealthSafety_OpenCloseSensor,
    SecurityHealthSafety_Smokebridge,
    SensorsActuators_IOLink,
    SwitchedLightingControl,
    SwitchedLightingControl_ApplianceLinc,
    SwitchedLightingControl_DinRail,
    SwitchedLightingControl_I3Outlet,
    SwitchedLightingControl_InLineLinc01,
    SwitchedLightingControl_InLineLinc02,
    SwitchedLightingControl_KeypadLinc_6,
    SwitchedLightingControl_KeypadLinc_8,
    SwitchedLightingControl_OnOffOutlet,
    SwitchedLightingControl_OutletLinc,
    SwitchedLightingControl_SwitchLinc01,
    SwitchedLightingControl_SwitchLinc02,
    SwitchedLightingControl_ToggleLinc,
    WindowCovering,
    X10Dimmable,
    X10OnOff,
    X10OnOffSensor,
)

from homeassistant.const import Platform

DEVICE_PLATFORM: dict[Device, dict[Platform, Iterable[int]]] = {
    AccessControl_Morningstar: {Platform.LOCK: [1]},
    DimmableLightingControl: {Platform.LIGHT: [1]},
    DimmableLightingControl_Dial: {Platform.LIGHT: [1]},
    DimmableLightingControl_DinRail: {Platform.LIGHT: [1]},
    DimmableLightingControl_FanLinc: {Platform.LIGHT: [1], Platform.FAN: [2]},
    DimmableLightingControl_InLineLinc01: {Platform.LIGHT: [1]},
    DimmableLightingControl_InLineLinc02: {Platform.LIGHT: [1]},
    DimmableLightingControl_KeypadLinc_6: {
        Platform.LIGHT: [1],
        Platform.SWITCH: [3, 4, 5, 6],
    },
    DimmableLightingControl_KeypadLinc_8: {
        Platform.LIGHT: [1],
        Platform.SWITCH: range(2, 9),
    },
    DimmableLightingControl_LampLinc: {Platform.LIGHT: [1]},
    DimmableLightingControl_OutletLinc: {Platform.LIGHT: [1]},
    DimmableLightingControl_SwitchLinc01: {Platform.LIGHT: [1]},
    DimmableLightingControl_SwitchLinc02: {Platform.LIGHT: [1]},
    DimmableLightingControl_ToggleLinc: {Platform.LIGHT: [1]},
    EnergyManagement_LoadController: {
        Platform.SWITCH: [1],
        Platform.BINARY_SENSOR: [2],
    },
    SecurityHealthSafety_DoorSensor: {Platform.BINARY_SENSOR: [1, 3, 4]},
    SecurityHealthSafety_LeakSensor: {Platform.BINARY_SENSOR: [2, 4]},
    SecurityHealthSafety_MotionSensor: {Platform.BINARY_SENSOR: [1, 2, 3]},
    SecurityHealthSafety_OpenCloseSensor: {Platform.BINARY_SENSOR: [1]},
    SecurityHealthSafety_Smokebridge: {Platform.BINARY_SENSOR: [1, 2, 3, 4, 6, 7]},
    SensorsActuators_IOLink: {Platform.SWITCH: [1], Platform.BINARY_SENSOR: [2]},
    SwitchedLightingControl: {Platform.SWITCH: [1]},
    SwitchedLightingControl_ApplianceLinc: {Platform.SWITCH: [1]},
    SwitchedLightingControl_DinRail: {Platform.SWITCH: [1]},
    SwitchedLightingControl_I3Outlet: {Platform.SWITCH: [1, 2]},
    SwitchedLightingControl_InLineLinc01: {Platform.SWITCH: [1]},
    SwitchedLightingControl_InLineLinc02: {Platform.SWITCH: [1]},
    SwitchedLightingControl_KeypadLinc_6: {
        Platform.SWITCH: [1, 3, 4, 5, 6],
    },
    SwitchedLightingControl_KeypadLinc_8: {
        Platform.SWITCH: range(1, 9),
    },
    SwitchedLightingControl_OnOffOutlet: {Platform.SWITCH: [1, 2]},
    SwitchedLightingControl_OutletLinc: {Platform.SWITCH: [1]},
    SwitchedLightingControl_SwitchLinc01: {Platform.SWITCH: [1]},
    SwitchedLightingControl_SwitchLinc02: {Platform.SWITCH: [1]},
    SwitchedLightingControl_ToggleLinc: {Platform.SWITCH: [1]},
    ClimateControl_Thermostat: {Platform.CLIMATE: [1]},
    ClimateControl_WirelessThermostat: {Platform.CLIMATE: [1]},
    WindowCovering: {Platform.COVER: [1]},
    X10Dimmable: {Platform.LIGHT: [1]},
    X10OnOff: {Platform.SWITCH: [1]},
    X10OnOffSensor: {Platform.BINARY_SENSOR: [1]},
}


def get_device_platforms(device) -> dict[Platform, Iterable[int]]:
    """Return the HA platforms for a device type."""
    return DEVICE_PLATFORM.get(type(device), {})


def get_device_platform_groups(device: Device, platform: Platform) -> Iterable[int]:
    """Return the list of device groups for a platform."""
    return get_device_platforms(device).get(platform, [])
