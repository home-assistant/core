"""The tests for Switch as X platforms."""

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.fan import FanEntityFeature
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.components.lock import LockState
from homeassistant.components.siren import SirenEntityFeature
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_OFF, STATE_ON, STATE_OPEN, Platform

PLATFORMS_TO_TEST = (
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
    Platform.VALVE,
)

CAPABILITY_MAP = {
    Platform.COVER: None,
    Platform.FAN: {},
    Platform.LIGHT: {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF]},
    Platform.LOCK: None,
    Platform.SIREN: None,
    Platform.VALVE: None,
}

STATE_MAP = {
    False: {
        Platform.COVER: {STATE_ON: STATE_OPEN, STATE_OFF: STATE_CLOSED},
        Platform.FAN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LIGHT: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LOCK: {STATE_ON: LockState.UNLOCKED, STATE_OFF: LockState.LOCKED},
        Platform.SIREN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.VALVE: {STATE_ON: STATE_OPEN, STATE_OFF: STATE_CLOSED},
    },
    True: {
        Platform.COVER: {STATE_ON: STATE_CLOSED, STATE_OFF: STATE_OPEN},
        Platform.FAN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LIGHT: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LOCK: {STATE_ON: LockState.LOCKED, STATE_OFF: LockState.UNLOCKED},
        Platform.SIREN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.VALVE: {STATE_ON: STATE_CLOSED, STATE_OFF: STATE_OPEN},
    },
}

SUPPORTED_FEATURE_MAP = {
    Platform.COVER: CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
    Platform.FAN: FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF,
    Platform.LIGHT: 0,
    Platform.LOCK: 0,
    Platform.SIREN: SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF,
    Platform.VALVE: ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE,
}
