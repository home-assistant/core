"""Constants for the ViCare integration."""
import enum

DOMAIN = "vicare"

PLATFORMS = ["climate", "sensor", "binary_sensor", "water_heater"]

VICARE_DEVICE_CONFIG = "device_conf"
VICARE_API = "api"
VICARE_NAME = "name"
VICARE_CIRCUITS = "circuits"

CONF_CIRCUIT = "circuit"
CONF_HEATING_TYPE = "heating_type"

DEFAULT_SCAN_INTERVAL = 60


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
