"""The tests for Binary sensor as X platforms."""

from homeassistant.const import STATE_CLOSED, STATE_OFF, STATE_ON, STATE_OPEN, Platform

PLATFORMS_TO_TEST = (Platform.COVER,)

STATE_MAP = {
    False: {
        Platform.COVER: {STATE_ON: STATE_OPEN, STATE_OFF: STATE_CLOSED},
    },
    True: {
        Platform.COVER: {STATE_ON: STATE_CLOSED, STATE_OFF: STATE_OPEN},
    },
}
