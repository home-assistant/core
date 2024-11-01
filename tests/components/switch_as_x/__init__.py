"""The tests for Switch as X platforms."""

from homeassistant.components.lock import LockState
from homeassistant.const import STATE_CLOSED, STATE_OFF, STATE_ON, STATE_OPEN, Platform

PLATFORMS_TO_TEST = (
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
    Platform.VALVE,
)

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
