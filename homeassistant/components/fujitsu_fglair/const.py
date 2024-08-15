"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""

from datetime import timedelta

from ayla_iot_unofficial.fujitsu_consts import (  # noqa: F401
    FGLAIR_APP_ID,
    FGLAIR_APP_SECRET,
)
from ayla_iot_unofficial.fujitsu_hvac import FanSpeed, OpMode, SwingMode

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    HVACMode,
)

API_TIMEOUT = 10
API_REFRESH = timedelta(minutes=5)

DOMAIN = "fujitsu_fglair"

CONF_EUROPE = "is_europe"

HA_TO_FUJI_FAN = {
    FAN_LOW: FanSpeed.LOW,
    FAN_MEDIUM: FanSpeed.MEDIUM,
    FAN_HIGH: FanSpeed.HIGH,
    FAN_AUTO: FanSpeed.AUTO,
}
FUJI_TO_HA_FAN = {value: key for key, value in HA_TO_FUJI_FAN.items()}

HA_TO_FUJI_HVAC = {
    HVACMode.OFF: OpMode.OFF,
    HVACMode.HEAT: OpMode.HEAT,
    HVACMode.COOL: OpMode.COOL,
    HVACMode.HEAT_COOL: OpMode.AUTO,
    HVACMode.DRY: OpMode.DRY,
    HVACMode.FAN_ONLY: OpMode.FAN,
}
FUJI_TO_HA_HVAC = {value: key for key, value in HA_TO_FUJI_HVAC.items()}

HA_TO_FUJI_SWING = {
    SWING_OFF: SwingMode.OFF,
    SWING_VERTICAL: SwingMode.SWING_VERTICAL,
    SWING_HORIZONTAL: SwingMode.SWING_HORIZONTAL,
    SWING_BOTH: SwingMode.SWING_BOTH,
}
FUJI_TO_HA_SWING = {value: key for key, value in HA_TO_FUJI_SWING.items()}
