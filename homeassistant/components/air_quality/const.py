"""Constants for the air_quality entity platform."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "air_quality"

ATTR_AQI: Final = "air_quality_index"
ATTR_CO2: Final = "carbon_dioxide"
ATTR_CO: Final = "carbon_monoxide"
ATTR_N2O: Final = "nitrogen_oxide"
ATTR_NO: Final = "nitrogen_monoxide"
ATTR_NO2: Final = "nitrogen_dioxide"
ATTR_OZONE: Final = "ozone"
ATTR_PM_0_1: Final = "particulate_matter_0_1"
ATTR_PM_10: Final = "particulate_matter_10"
ATTR_PM_2_5: Final = "particulate_matter_2_5"
ATTR_SO2: Final = "sulphur_dioxide"


class AirQualityEntityStateAttribute(StrEnum):
    """State attributes for air quality entities."""

    AIR_QUALITY_INDEX = "air_quality_index"
    CARBON_DIOXIDE = "carbon_dioxide"
    CARBON_MONOXIDE = "carbon_monoxide"
    NITROGEN_DIOXIDE = "nitrogen_dioxide"
    NITROGEN_MONOXIDE = "nitrogen_monoxide"
    NITROGEN_OXIDE = "nitrogen_oxide"
    OZONE = "ozone"
    PARTICULATE_MATTER_0_1 = "particulate_matter_0_1"
    PARTICULATE_MATTER_10 = "particulate_matter_10"
    PARTICULATE_MATTER_2_5 = "particulate_matter_2_5"
    SULPHUR_DIOXIDE = "sulphur_dioxide"
