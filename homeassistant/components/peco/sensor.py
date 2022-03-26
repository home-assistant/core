"""Sensor component for PECO outage counter."""

from typing import Final

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_COUNTY, DOMAIN

PARALLEL_UPDATES: Final = 0
SENSOR_LIST = (
    SensorEntityDescription(key="customers_out", name="Customers Out"),
    SensorEntityDescription(
        key="percent_customers_out",
        name="Percent Customers Out",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(key="outage_count", name="Outage Count"),
    SensorEntityDescription(key="customers_served", name="Customers Served"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    county: str = config_entry.data[CONF_COUNTY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [PecoSensor(sensor, county, coordinator) for sensor in SENSOR_LIST],
        True,
    )
    return


class PecoSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, float]]], SensorEntity
):
    """PECO outage counter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:power-plug-off"

    def __init__(
        self,
        description: SensorEntityDescription,
        county: str,
        coordinator: DataUpdateCoordinator[dict[str, float]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{county.capitalize()} {description.name}"
        self._attr_unique_id = f"{county}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the value of the sensor."""
        return self.coordinator.data[self.entity_description.key]
