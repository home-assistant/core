"""Constants for the ViCare integration."""
import enum

from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    ENERGY_KILO_WATT_HOUR,
    VOLUME_CUBIC_METERS,
)

DOMAIN = "vicare"

PLATFORMS = ["climate", "sensor", "binary_sensor", "water_heater"]

VICARE_DEVICE_CONFIG = "device_conf"
VICARE_API = "api"
VICARE_CIRCUITS = "circuits"

CONF_CIRCUIT = "circuit"
CONF_HEATING_TYPE = "heating_type"

DEFAULT_SCAN_INTERVAL = 60

VICARE_CUBIC_METER = "cubicMeter"
VICARE_KWH = "kilowattHour"

VICARE_UNIT_TO_DEVICE_CLASS = {
    VICARE_KWH: DEVICE_CLASS_ENERGY,
    VICARE_CUBIC_METER: DEVICE_CLASS_GAS,
}

VICARE_UNIT_TO_UNIT_OF_MEASUREMENT = {
    VICARE_KWH: ENERGY_KILO_WATT_HOUR,
    VICARE_CUBIC_METER: VOLUME_CUBIC_METERS,
}


class HeatingType(enum.Enum):
    """Possible options for heating type."""

    auto = "auto"
    gas = "gas"
    oil = "oil"
    pellets = "pellets"
    heatpump = "heatpump"
    fuelcell = "fuelcell"


DEFAULT_HEATING_TYPE = HeatingType.auto

HEATING_TYPE_TO_CREATOR_METHOD = {
    HeatingType.auto: "asAutoDetectDevice",
    HeatingType.gas: "asGazBoiler",
    HeatingType.fuelcell: "asFuelCell",
    HeatingType.heatpump: "asHeatPump",
    HeatingType.oil: "asOilBoiler",
    HeatingType.pellets: "asPelletsBoiler",
}
