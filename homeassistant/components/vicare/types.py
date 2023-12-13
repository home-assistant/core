"""ViCare types."""
from enum import StrEnum


# Heating programs
class HeatingProgram(StrEnum):
    """ViCare preset heating programs.

    As listed in https://github.com/somm15/PyViCare/blob/8ba411483a865e074d1146fd1b8b7a8c4f4be122/PyViCare/PyViCareHeatingDevice.py#L564C27-L564C27
    """

    ACTIVE = "active"
    COMFORT = "comfort"
    COMFORT_COOLING = "comfortCooling"
    COMFORT_COOLING_ECO = "comfortCoolingEnergySaving"
    COMFORT_ECO = "comfortEnergySaving"
    COMFORT_HEATING = "comfortHeating"
    DHW_PRECEDENCE = "dhwPrecedence"
    ECO = "eco"
    EXTERNAL = "external"
    FIXED = "fixed"
    FORCED = "forcedLastFromSchedule"
    FROST_PROTECTION = "frostprotection"
    HOLIDAY = "holiday"
    HOLIDAY_AT_HOME = "holidayAtHome"
    MANUAL = "manual"
    NORMAL = "normal"
    NORMAL_COOLING = "normalCooling"
    NORMAL_COOLING_ECO = "normalCoolingEnergySaving"
    NORMAL_ECO = "normalEnergySaving"
    NORMAL_HEATING = "normalHeating"
    REDUCED = "reduced"
    REDUCED_COOLING = "reducedCooling'"
    REDUCED_COOLING_ECO = "reducedCoolingEnergySaving"
    REDUCED_ECO = "reducedEnergySaving"
    REDUCED_HEATING = "reducedHeating"
    STANDBY = "standby"
    SUMMER_ECO = "summerEco"
