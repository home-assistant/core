"""RKI Covid numbers sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_COUNTY, ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "count": "mdi:virus",
    "deaths": "mdi:cross",
    "recovered": "mdi:bottle-tonic-plus-outline",
    "week_incidence": "mdi:clipboard-pulse",
    "cases_per100k": "mdi:home-group",
    "new_cases": "mdi:shield-bug",
    "new_deaths": "mdi:shield-cross",
    "new_recovered": "mdi:shield-sync",
}

DISTRICT_SENSORS = {
    "hospitalization_cases_baby": "mdi:baby-face-outline",
    "hospitalization_incidence_baby": "mdi:baby-face",
    "hospitalization_cases_children": "mdi:account-child-outline",
    "hospitalization_incidence_children": "mdi:account-child",
    "hospitalization_cases_teen": "mdi:face-woman",
    "hospitalization_incidence_teen": "mdi:face-woman-outline",
    "hospitalization_cases_grown": "mdi:face-man",
    "hospitalization_incidence_grown": "mdi:face-man-outline",
    "hospitalization_cases_senior": "mdi:account-cowboy-hat-outline",
    "hospitalization_incidence_senior": "mdi:account-cowboy-hat",
    "hospitalization_cases_old": "mdi:human-white-cane",
    "hospitalization_incidence_old": "mdi:human-cane",
}


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors from a config entry in the integrations UI."""
    _LOGGER.debug("create sensor from config entry %s", config_entry.data)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    district = config_entry.data[ATTR_COUNTY]
    sensors = [
        RKICovidNumbersSensor(coordinator, district, info_type) for info_type in SENSORS
    ]
    async_add_entities(sensors, update_before_add=True)

    # add additional sensors for districts
    if district.startswith("BL"):
        district_sensors = [
            RKICovidNumbersSensor(coordinator, district, info_type)
            for info_type in DISTRICT_SENSORS
        ]
        async_add_entities(district_sensors, update_before_add=True)


class RKICovidNumbersSensor(SensorEntity, CoordinatorEntity):
    """Representation of a sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        district: dict[str, str],
        info_type: str,
    ) -> None:
        """Initialize a new sensor."""
        _LOGGER.debug("initialize %s sensor for %s", info_type, district)
        super().__init__(coordinator)

        data = coordinator.data[district]

        if data.county:
            self._attr_name = f"{data.county} {info_type}"
        else:
            self._attr_name = f"{data.name} {info_type}"

        self._attr_unique_id = f"{district}.{info_type}"

        self.district = district
        self.info_type = info_type
        self._attr_native_unit_of_measurement = self._measurement_unit()
        self._attr_native_value = self._native_value()
        self._attr_icon = {**SENSORS, **DISTRICT_SENSORS}[self.info_type]

    def _native_value(self):
        return getattr(self.coordinator.data[self.district], self.info_type)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.district in self.coordinator.data

    def _measurement_unit(self) -> str:
        """Return unit of measurement."""
        if self.info_type in ("count", "deaths", "recovered"):
            return "people"

        if self.info_type in (
            "week_incidence",
            "hospitalization_incidence_baby",
            "hospitalization_incidence_children",
            "hospitalization_incidence_teen",
            "hospitalization_incidence_grown",
            "hospitalization_incidence_senior",
            "hospitalization_incidence_old",
        ):
            return "nb"
        return "cases"
