"""Constants for the ViCare integration."""
import enum

from homeassistant.const import Platform, UnitOfEnergy, UnitOfVolume

DOMAIN = "vicare"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

DEVICE_LIST = "device_list"
VICARE_NAME = "ViCare"

CONF_CIRCUIT = "circuit"
CONF_HEATING_TYPE = "heating_type"

DEFAULT_CACHE_DURATION = 60

VICARE_CUBIC_METER = "cubicMeter"
VICARE_KWH = "kilowattHour"


VICARE_UNIT_TO_UNIT_OF_MEASUREMENT = {
    VICARE_KWH: UnitOfEnergy.KILO_WATT_HOUR,
    VICARE_CUBIC_METER: UnitOfVolume.CUBIC_METERS,
}


class HeatingProgram(enum.StrEnum):
    """ViCare preset heating programs.

    As listed inhttps://github.com/somm15/PyViCare/blob/63f9f7fea505fdf9a26c77c6cd0bff889abcdb05/PyViCare/PyViCareHeatingDevice.py#L606
    """

    COMFORT = "comfort"
    COMFORT_HEATING = "comfortHeating"
    ECO = "eco"
    NORMAL = "normal"
    NORMAL_HEATING = "normalHeating"
    REDUCED = "reduced"
    REDUCED_HEATING = "reducedHeating"
    STANDBY = "standby"


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
