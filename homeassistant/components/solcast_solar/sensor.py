"""Support for the Solcast Solar sensor service."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import (SensorEntity,
                                                SensorEntityDescription)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_IDENTIFIERS, ATTR_MANUFACTURER,
                                    ATTR_MODEL, ATTR_NAME, DEVICE_CLASS_ENERGY,
                                    DEVICE_CLASS_TIMESTAMP, ENERGY_KILO_WATT_HOUR)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                        DataUpdateCoordinator)

from . import SolcastDataCoordinator
from .const import ATTR_ENTRY_TYPE, ATTRIBUTION, DOMAIN, ENTRY_TYPE_SERVICE

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="energy_production_forecast_today",
        name="Forecast - Today",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="sum_energy_production_remaining_today",
        name="Forecast - Remaining Today",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="energy_production_forecast_tomorrow",
        name="Forecast - Tomorrow",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="energy_this_hour",
        name="Forecast - This Hour",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="energy_next_hour",
        name="Forecast - Next Hour",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="last_update",
        name="API Data Updated",
        device_class=DEVICE_CLASS_TIMESTAMP,
        icon="mdi:clock",
    ),
    SensorEntityDescription(
        key="solcast_api_poll_counter",
        name="API calls remaining",
        entity_registry_enabled_default=False,
        device_class="api_count",
        icon="mdi:cloud-download-outline"
    ),
)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Defer sensor setup to the shared sensor module."""

    coordinator: SolcastDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SolcastSensor(
            entry_id=entry.entry_id,
            coordinator=coordinator,
            entity_description=description,
            myIntegrationName=entry.title
        ) 
        for description in SENSOR_TYPES
    )


class SolcastSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing Solcast Sensor data."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: DataUpdateCoordinator, #SolcastDataCoordinator
        entity_description: SensorEntityDescription,
        myIntegrationName: str,
    ) -> None:
        """Initialize Forcast.Solar sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self.entity_id = f"{SENSOR_DOMAIN}.{entity_description.key}"
        self._attr_unique_id = f"{entry_id}_{entity_description.key}"

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, entry_id)},
            ATTR_NAME: myIntegrationName ,
            ATTR_MANUFACTURER: "Solcast Solar",
            ATTR_MODEL: "Solcast API",
            ATTR_ENTRY_TYPE: ENTRY_TYPE_SERVICE,
        }

    @property
    def native_value(self):
        """State of the sensor."""
        
        state = self.coordinator.data[self.entity_description.key]

        if isinstance(state, datetime):
            return state.isoformat()
        return state

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return False
