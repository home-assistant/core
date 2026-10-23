"""Base entity for the Air quality platform."""

from typing import Any, Final, final, override

from homeassistant.const import UnitOfDensity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_AQI,
    ATTR_CO,
    ATTR_CO2,
    ATTR_N2O,
    ATTR_NO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_0_1,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
)

PROP_TO_ATTR: Final[dict[str, str]] = {
    "air_quality_index": ATTR_AQI,
    "carbon_dioxide": ATTR_CO2,
    "carbon_monoxide": ATTR_CO,
    "nitrogen_oxide": ATTR_N2O,
    "nitrogen_monoxide": ATTR_NO,
    "nitrogen_dioxide": ATTR_NO2,
    "ozone": ATTR_OZONE,
    "particulate_matter_0_1": ATTR_PM_0_1,
    "particulate_matter_10": ATTR_PM_10,
    "particulate_matter_2_5": ATTR_PM_2_5,
    "sulphur_dioxide": ATTR_SO2,
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
