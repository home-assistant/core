"""Utility methods for the Insteon platform."""
from pyinsteon.device_types.ipdb import (
    AccessControl_Morningstar,
    ClimateControl_Thermostat,
    ClimateControl_WirelessThermostat,
    DimmableLightingControl,
    DimmableLightingControl_DinRail,
    DimmableLightingControl_FanLinc,
    DimmableLightingControl_InLineLinc,
    DimmableLightingControl_KeypadLinc_6,
    DimmableLightingControl_KeypadLinc_8,
    DimmableLightingControl_LampLinc,
    DimmableLightingControl_OutletLinc,
    DimmableLightingControl_SwitchLinc,
    DimmableLightingControl_ToggleLinc,
    EnergyManagement_LoadController,
    GeneralController_ControlLinc,
    GeneralController_MiniRemote_4,
    GeneralController_MiniRemote_8,
    GeneralController_MiniRemote_Switch,
    GeneralController_RemoteLinc,
    SecurityHealthSafety_DoorSensor,
    SecurityHealthSafety_LeakSensor,
    SecurityHealthSafety_MotionSensor,
    SecurityHealthSafety_OpenCloseSensor,
    SecurityHealthSafety_Smokebridge,
    SensorsActuators_IOLink,
    SwitchedLightingControl,
    SwitchedLightingControl_ApplianceLinc,
    SwitchedLightingControl_DinRail,
    SwitchedLightingControl_InLineLinc,
    SwitchedLightingControl_KeypadLinc_6,
    SwitchedLightingControl_KeypadLinc_8,
    SwitchedLightingControl_OnOffOutlet,
    SwitchedLightingControl_OutletLinc,
    SwitchedLightingControl_SwitchLinc,
    SwitchedLightingControl_ToggleLinc,
    WindowCovering,
    X10Dimmable,
    X10OnOff,
    X10OnOffSensor,
)

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.switch import DOMAIN as SWITCH

from .const import ON_OFF_EVENTS

DEVICE_PLATFORM = {
    AccessControl_Morningstar: {LOCK: [1]},
    DimmableLightingControl: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_DinRail: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_FanLinc: {LIGHT: [1], FAN: [2], ON_OFF_EVENTS: [1, 2]},
    DimmableLightingControl_InLineLinc: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_KeypadLinc_6: {
        LIGHT: [1],
        SWITCH: [3, 4, 5, 6],
        ON_OFF_EVENTS: [1, 3, 4, 5, 6],
    },
    DimmableLightingControl_KeypadLinc_8: {
        LIGHT: [1],
        SWITCH: range(2, 9),
        ON_OFF_EVENTS: range(1, 9),
    },
    DimmableLightingControl_LampLinc: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_OutletLinc: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_SwitchLinc: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    DimmableLightingControl_ToggleLinc: {LIGHT: [1], ON_OFF_EVENTS: [1]},
    EnergyManagement_LoadController: {SWITCH: [1], BINARY_SENSOR: [2]},
    GeneralController_ControlLinc: {ON_OFF_EVENTS: [1]},
    GeneralController_MiniRemote_4: {ON_OFF_EVENTS: range(1, 5)},
    GeneralController_MiniRemote_8: {ON_OFF_EVENTS: range(1, 9)},
    GeneralController_MiniRemote_Switch: {ON_OFF_EVENTS: [1, 2]},
    GeneralController_RemoteLinc: {ON_OFF_EVENTS: [1]},
    SecurityHealthSafety_DoorSensor: {BINARY_SENSOR: [1, 3, 4], ON_OFF_EVENTS: [1]},
    SecurityHealthSafety_LeakSensor: {BINARY_SENSOR: [2, 4]},
    SecurityHealthSafety_MotionSensor: {BINARY_SENSOR: [1, 2, 3], ON_OFF_EVENTS: [1]},
    SecurityHealthSafety_OpenCloseSensor: {BINARY_SENSOR: [1]},
    SecurityHealthSafety_Smokebridge: {BINARY_SENSOR: [1, 2, 3, 4, 6, 7]},
    SensorsActuators_IOLink: {SWITCH: [1], BINARY_SENSOR: [2], ON_OFF_EVENTS: [1, 2]},
    SwitchedLightingControl: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_ApplianceLinc: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_DinRail: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_InLineLinc: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_KeypadLinc_6: {
        SWITCH: [1, 3, 4, 5, 6],
        ON_OFF_EVENTS: [1, 3, 4, 5, 6],
    },
    SwitchedLightingControl_KeypadLinc_8: {
        SWITCH: range(1, 9),
        ON_OFF_EVENTS: range(1, 9),
    },
    SwitchedLightingControl_OnOffOutlet: {SWITCH: [1, 2], ON_OFF_EVENTS: [1, 2]},
    SwitchedLightingControl_OutletLinc: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_SwitchLinc: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    SwitchedLightingControl_ToggleLinc: {SWITCH: [1], ON_OFF_EVENTS: [1]},
    ClimateControl_Thermostat: {CLIMATE: [1]},
    ClimateControl_WirelessThermostat: {CLIMATE: [1]},
    WindowCovering: {COVER: [1]},
    X10Dimmable: {LIGHT: [1]},
    X10OnOff: {SWITCH: [1]},
    X10OnOffSensor: {BINARY_SENSOR: [1]},
}


def get_device_platforms(device):
    """Return the HA platforms for a device type."""
    return DEVICE_PLATFORM.get(type(device), {}).keys()


def get_platform_groups(device, domain) -> dict:
    """Return the platforms that a device belongs in."""
    return DEVICE_PLATFORM.get(type(device), {}).get(domain, {})  # type: ignore[attr-defined]
