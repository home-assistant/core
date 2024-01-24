"""The tests for Switch as X platforms."""

from homeassistant.const import (
    STATE_CLOSED,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNLOCKED,
    Platform,
)

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
        Platform.LOCK: {STATE_ON: STATE_UNLOCKED, STATE_OFF: STATE_LOCKED},
        Platform.SIREN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.VALVE: {STATE_ON: STATE_OPEN, STATE_OFF: STATE_CLOSED},
    },
    True: {
        Platform.COVER: {STATE_ON: STATE_CLOSED, STATE_OFF: STATE_OPEN},
        Platform.FAN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LIGHT: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.LOCK: {STATE_ON: STATE_LOCKED, STATE_OFF: STATE_UNLOCKED},
        Platform.SIREN: {STATE_ON: STATE_ON, STATE_OFF: STATE_OFF},
        Platform.VALVE: {STATE_ON: STATE_CLOSED, STATE_OFF: STATE_OPEN},
    },
}
