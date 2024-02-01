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

VICARE_DEVICE_CONFIG = "device_conf"
VICARE_DEVICE_CONFIG_LIST = "device_config_list"
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


class HeatingProgram(enum.StrEnum):
    """ViCare preset heating programs.

    As listed inhttps://github.com/somm15/PyViCare/blob/63f9f7fea505fdf9a26c77c6cd0bff889abcdb05/PyViCare/PyViCareHeatingDevice.py#L606
    """

    # ACTIVE = "active"
    COMFORT = "comfort"
    # COMFORT_COOLING = "comfortCooling"
    # COMFORT_COOLING_ECO = "comfortCoolingEnergySaving"
    # COMFORT_ECO = "comfortEnergySaving"
    COMFORT_HEATING = "comfortHeating"
    # DHW_PRECEDENCE = "dhwPrecedence"
    ECO = "eco"
    # EXTERNAL = "external"
    # FIXED = "fixed"
    # FORCED = "forcedLastFromSchedule"
    # FROST_PROTECTION = "frostprotection"
    # HOLIDAY = "holiday"
    # HOLIDAY_AT_HOME = "holidayAtHome"
    # MANUAL = "manual"
    NORMAL = "normal"
    # NORMAL_COOLING = "normalCooling"
    # NORMAL_COOLING_ECO = "normalCoolingEnergySaving"
    # NORMAL_ECO = "normalEnergySaving"
    NORMAL_HEATING = "normalHeating"
    REDUCED = "reduced"
    # REDUCED_COOLING = "reducedCooling'"
    # REDUCED_COOLING_ECO = "reducedCoolingEnergySaving"
    # REDUCED_ECO = "reducedEnergySaving"
    REDUCED_HEATING = "reducedHeating"
    STANDBY = "standby"
    # SUMMER_ECO = "summerEco"


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
