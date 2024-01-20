"""Constants for the teslemetry tests."""

from homeassistant.components.teslemetry.const import TeslemetryState
from homeassistant.const import CONF_ACCESS_TOKEN

CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}

WAKE_UP_SUCCESS = {"response": {"state": TeslemetryState.ONLINE}, "error": None}
WAKE_UP_FAILURE = {"response": {"state": TeslemetryState.OFFLINE}, "error": None}
