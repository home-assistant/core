"""Support for the AirNow sensor service."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirNowDataUpdateCoordinator
from .const import (
    ATTR_API_AQI,
    ATTR_API_AQI_DESCRIPTION,
    ATTR_API_AQI_LEVEL,
    ATTR_API_O3,
    ATTR_API_PM25,
    DOMAIN,
    SENSOR_AQI_ATTR_DESCR,
    SENSOR_AQI_ATTR_LEVEL,
)

ATTRIBUTION = "Data provided by AirNow"

PARALLEL_UPDATES = 1

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_AQI,
        icon="mdi:blur",
        name=ATTR_API_AQI,
        native_unit_of_measurement="aqi",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PM25,
        icon="mdi:blur",
        name=ATTR_API_PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_O3,
        icon="mdi:blur",
        name=ATTR_API_O3,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirNow sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [AirNowSensor(coordinator, description) for description in SENSOR_TYPES]

    async_add_entities(entities, False)


class AirNowSensor(CoordinatorEntity[AirNowDataUpdateCoordinator], SensorEntity):
    """Define an AirNow sensor."""

    def __init__(
        self,
        coordinator: AirNowDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._state = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_name = f"AirNow {description.name}"
        self._attr_unique_id = (
            f"{coordinator.latitude}-{coordinator.longitude}-{description.key.lower()}"
        )

    @property
    def native_value(self):
        """Return the state."""
        self._state = self.coordinator.data.get(self.entity_description.key)

        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.entity_description.key == ATTR_API_AQI:
            self._attrs[SENSOR_AQI_ATTR_DESCR] = self.coordinator.data[
                ATTR_API_AQI_DESCRIPTION
            ]
            self._attrs[SENSOR_AQI_ATTR_LEVEL] = self.coordinator.data[
                ATTR_API_AQI_LEVEL
            ]

        return self._attrs
