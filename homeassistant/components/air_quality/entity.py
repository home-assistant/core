"""Base entity for the Air quality platform."""

from typing import Any, Final, final, override

from homeassistant.const import UnitOfDensity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from .const import AirQualityEntityStateAttribute

PROP_TO_ATTR: Final[dict[str, AirQualityEntityStateAttribute]] = {
    "air_quality_index": AirQualityEntityStateAttribute.AIR_QUALITY_INDEX,
    "carbon_dioxide": AirQualityEntityStateAttribute.CARBON_DIOXIDE,
    "carbon_monoxide": AirQualityEntityStateAttribute.CARBON_MONOXIDE,
    "nitrogen_oxide": AirQualityEntityStateAttribute.NITROGEN_OXIDE,
    "nitrogen_monoxide": AirQualityEntityStateAttribute.NITROGEN_MONOXIDE,
    "nitrogen_dioxide": AirQualityEntityStateAttribute.NITROGEN_DIOXIDE,
    "ozone": AirQualityEntityStateAttribute.OZONE,
    "particulate_matter_0_1": AirQualityEntityStateAttribute.PARTICULATE_MATTER_0_1,
    "particulate_matter_10": AirQualityEntityStateAttribute.PARTICULATE_MATTER_10,
    "particulate_matter_2_5": AirQualityEntityStateAttribute.PARTICULATE_MATTER_2_5,
    "sulphur_dioxide": AirQualityEntityStateAttribute.SULPHUR_DIOXIDE,
}


class AirQualityEntity(Entity):
    """ABC for air quality data."""

    @property
    def particulate_matter_2_5(self) -> StateType:
        """Return the particulate matter 2.5 level."""
        raise NotImplementedError

    @property
    def particulate_matter_10(self) -> StateType:
        """Return the particulate matter 10 level."""
        return None

    @property
    def particulate_matter_0_1(self) -> StateType:
        """Return the particulate matter 0.1 level."""
        return None

    @property
    def air_quality_index(self) -> StateType:
        """Return the Air Quality Index (AQI)."""
        return None

    @property
    def ozone(self) -> StateType:
        """Return the O3 (ozone) level."""
        return None

    @property
    def carbon_monoxide(self) -> StateType:
        """Return the CO (carbon monoxide) level."""
        return None

    @property
    def carbon_dioxide(self) -> StateType:
        """Return the CO2 (carbon dioxide) level."""
        return None

    @property
    def sulphur_dioxide(self) -> StateType:
        """Return the SO2 (sulphur dioxide) level."""
        return None

    @property
    def nitrogen_oxide(self) -> StateType:
        """Return the N2O (nitrogen oxide) level."""
        return None

    @property
    def nitrogen_monoxide(self) -> StateType:
        """Return the NO (nitrogen monoxide) level."""
        return None

    @property
    def nitrogen_dioxide(self) -> StateType:
        """Return the NO2 (nitrogen dioxide) level."""
        return None

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        data: dict[str, str | int | float] = {}

        for prop, attr in PROP_TO_ATTR.items():
            if (value := getattr(self, prop)) is not None:
                data[attr] = value

        return data

    @property
    @override
    def state(self) -> StateType:
        """Return the current state."""
        return self.particulate_matter_2_5

    @property
    @override
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
