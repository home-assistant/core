"""Constants for the ScreenLogic integration."""
from screenlogicpy.const.common import UNIT
from screenlogicpy.const.data import SHARED_VALUES
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

ScreenLogicDataPath = tuple[str | int, ...]

DOMAIN = "screenlogic"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

SERVICE_SET_COLOR_MODE = "set_color_mode"
ATTR_COLOR_MODE = "color_mode"
SUPPORTED_COLOR_MODES = {slugify(cm.name): cm.value for cm in COLOR_MODE}

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


def generate_unique_id(
    device: str | int, group: str | int | None, data_key: str | int
) -> str:
    """Generate new unique_id for a screenlogic entity from specified parameters."""
    if data_key in SHARED_VALUES and device is not None:
        return (
            f"{device}_{group}_{data_key}"
            if group is not None and (isinstance(group, int) or group.isdigit())
            else f"{device}_{data_key}"
        )
    return str(data_key)
