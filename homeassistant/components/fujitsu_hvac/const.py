"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""
from ayla_iot_unofficial.fujitsu_hvac import FanSpeed, OpMode, SwingMode
from bidict import bidict

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

DOMAIN = "fujitsu_hvac"
AYLA_APP_ID = "CJIOSP-id"
AYLA_APP_SECRET = "CJIOSP-Vb8MQL_lFiYQ7DKjN0eCFXznKZE"

CONF_EUROPE = "is_europe"
CONF_DEVICE = "device"

NO_DEVICES_ERROR = "No devices found."

FAN_MODE_MAP = bidict(
    {
        FAN_LOW: FanSpeed.LOW,
        FAN_MEDIUM: FanSpeed.MEDIUM,
        FAN_HIGH: FanSpeed.HIGH,
        FAN_AUTO: FanSpeed.AUTO,
    }
)

HVAC_MODE_MAP = bidict(
    {
        HVACMode.OFF: OpMode.OFF,
        HVACMode.HEAT: OpMode.HEAT,
        HVACMode.COOL: OpMode.COOL,
        HVACMode.AUTO: OpMode.AUTO,
        HVACMode.DRY: OpMode.DRY,
        HVACMode.FAN_ONLY: OpMode.FAN,
    }
)

SWING_MODE_MAP = bidict(
    {
        SWING_OFF: SwingMode.OFF,
        SWING_VERTICAL: SwingMode.SWING_VERTICAL,
        SWING_HORIZONTAL: SwingMode.SWING_HORIZONTAL,
        SWING_BOTH: SwingMode.SWING_BOTH,
    }
)
