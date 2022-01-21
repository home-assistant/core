"""RKI Covid numbers sensor."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.rki_covid.coordinator import RkiCovidDataUpdateCoordinator
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_COUNTY, ATTRIBUTION, CONF_DISTRICT_NAME, CONF_DISTRICTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "count": "mdi:virus",
    "deaths": "mdi:cross",
    "recovered": "mdi:bottle-tonic-plus-outline",
    "weekIncidence": "mdi:clipboard-pulse",
    "casesPer100k": "mdi:home-group",
    "newCases": "mdi:shield-bug",
    "newDeaths": "mdi:shield-cross",
    "newRecovered": "mdi:shield-sync",
}

DISTRICT_SENSORS = {
    "hospitalizationCasesBaby": "mdi:baby-face-outline",
    "hospitalizationIncidenceBaby": "mdi:baby-face",
    "hospitalizationCasesChildren": "mdi:account-child-outline",
    "hospitalizationIncidenceChildren": "mdi:account-child",
    "hospitalizationCasesTeen": "mdi:face-woman",
    "hospitalizationIncidenceTeen": "mdi:face-woman-outline",
    "hospitalizationCasesGrown": "mdi:face-man",
    "hospitalizationIncidenceGrown": "mdi:face-man-outline",
    "hospitalizationCasesSenior": "mdi:account-cowboy-hat-outline",
    "hospitalizationIncidenceSenior": "mdi:account-cowboy-hat",
    "hospitalizationCasesOld": "mdi:human-white-cane",
    "hospitalizationIncidenceOld": "mdi:human-cane",
}


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    coordinator = RkiCovidDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    if coordinator is None or coordinator.data is None:
        raise PlatformNotReady("Data coordinator could not be initialized!")

    districts = config[CONF_DISTRICTS]

    # district sensors
    sensors = [
        RKICovidNumbersSensor(coordinator, district[CONF_DISTRICT_NAME], info_type)
        for info_type in SENSORS
        for district in districts
    ]
    async_add_entities(sensors, update_before_add=True)

    # sensors on state level (additional sensors)
    for district in districts:
        if district.startswith("BL"):
            district_sensors = [
                RKICovidNumbersSensor(coordinator, district, info_type)
                for info_type in DISTRICT_SENSORS
            ]
            async_add_entities(district_sensors, update_before_add=True)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Create sensors from a config entry in the integrations UI."""
    _LOGGER.debug(f"create sensor from config entry {config_entry.data}")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator is None or coordinator.data is None:
        raise PlatformNotReady("Data coordinator could not be initialized!")

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
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        district: dict[str, str],
        info_type: str,
    ) -> None:
        """Initialize a new sensor."""
        _LOGGER.debug(f"initialize {info_type} sensor for {district}")
        super().__init__(coordinator)

        data = coordinator.data[district]

        if data.county:
            self._attr_name = f"{data.county} {info_type}"
        else:
            self._attr_name = f"{data.name} {info_type}"

        self._attr_unique_id = f"{district}.{info_type}"

        self.district = district
        self.info_type = info_type
        self.updated = datetime.now()
        self._attr_native_unit_of_measurement = self._measurement_unit()
        self._attr_native_value = self._native_value()
        self._attr_icon = {**SENSORS, **DISTRICT_SENSORS}[self.info_type]

    def _native_value(self):
        return getattr(self.coordinator.data[self.district], self.info_type)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.district in self.coordinator.data
        )

    def _measurement_unit(self) -> str:
        """Return unit of measurement."""
        if self.info_type in ("count", "deaths", "recovered"):
            return "people"
        elif self.info_type in (
            "weekIncidence",
            "hospitalizationIncidenceBaby",
            "hospitalizationIncidenceChildren",
            "hospitalizationIncidenceTeen",
            "hospitalizationIncidenceGrown",
            "hospitalizationIncidenceSenior",
            "hospitalizationIncidenceOld",
        ):
            return "nb"
        else:
            return "cases"
