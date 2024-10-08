"""Constants for the ScreenLogic integration."""

from screenlogicpy.const.common import UNIT
from screenlogicpy.device_const.circuit import FUNCTION
from screenlogicpy.device_const.system import COLOR_MODE

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.util import slugify

type ScreenLogicDataPath = tuple[str | int, ...]

DOMAIN = "screenlogic"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

ATTR_CONFIG_ENTRY = "config_entry"

SERVICE_SET_COLOR_MODE = "set_color_mode"
ATTR_COLOR_MODE = "color_mode"
SUPPORTED_COLOR_MODES = {slugify(cm.name): cm.value for cm in COLOR_MODE}

SERVICE_START_SUPER_CHLORINATION = "start_super_chlorination"
ATTR_RUNTIME = "runtime"
MAX_RUNTIME = 72
MIN_RUNTIME = 0

SERVICE_STOP_SUPER_CHLORINATION = "stop_super_chlorination"

LIGHT_CIRCUIT_FUNCTIONS = {
    FUNCTION.COLOR_WHEEL,
    FUNCTION.DIMMER,
    FUNCTION.INTELLIBRITE,
    FUNCTION.LIGHT,
    FUNCTION.MAGICSTREAM,
    FUNCTION.PHOTONGEN,
    FUNCTION.SAL_LIGHT,
    FUNCTION.SAM_LIGHT,
}

SL_UNIT_TO_HA_UNIT = {
    UNIT.CELSIUS: UnitOfTemperature.CELSIUS,
    UNIT.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
    UNIT.MILLIVOLT: UnitOfElectricPotential.MILLIVOLT,
    UNIT.WATT: UnitOfPower.WATT,
    UNIT.HOUR: UnitOfTime.HOURS,
    UNIT.SECOND: UnitOfTime.SECONDS,
    UNIT.REVOLUTIONS_PER_MINUTE: REVOLUTIONS_PER_MINUTE,
    UNIT.PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    UNIT.PERCENT: PERCENTAGE,
}
