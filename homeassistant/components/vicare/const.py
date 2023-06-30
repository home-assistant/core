"""Constants for the ViCare integration."""
import enum

from homeassistant.const import Platform, UnitOfEnergy, UnitOfVolume

DOMAIN = "vicare"

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.WATER_HEATER,
]

VICARE_DEVICE_CONFIG = "device_conf"
VICARE_API = "api"
VICARE_NAME = "ViCare"

CONF_CIRCUIT = "circuit"
CONF_HEATING_TYPE = "heating_type"

DEFAULT_SCAN_INTERVAL = 60

VICARE_CUBIC_METER = "cubicMeter"
VICARE_KWH = "kilowattHour"


VICARE_UNIT_TO_UNIT_OF_MEASUREMENT = {
    VICARE_KWH: UnitOfEnergy.KILO_WATT_HOUR,
    VICARE_CUBIC_METER: UnitOfVolume.CUBIC_METERS,
}


class HeatingType(enum.Enum):
    """Possible options for heating type."""

    auto = "auto"
    gas = "gas"
    oil = "oil"
    pellets = "pellets"
    heatpump = "heatpump"
    fuelcell = "fuelcell"
    hybrid = "hybrid"


DEFAULT_HEATING_TYPE = HeatingType.auto

HEATING_TYPE_TO_CREATOR_METHOD = {
    HeatingType.auto: "asAutoDetectDevice",
    HeatingType.gas: "asGazBoiler",
    HeatingType.fuelcell: "asFuelCell",
    HeatingType.heatpump: "asHeatPump",
    HeatingType.oil: "asOilBoiler",
    HeatingType.pellets: "asPelletsBoiler",
    HeatingType.hybrid: "asHybridDevice",
}
