"""Support for the Airzone sensors."""
from __future__ import annotations

from aioairzone.const import AZD_NAME, AZD_SYSTEMS, AZD_ZONES

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SENSOR_TYPES
from .coordinator import AirzoneUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for system_id, system_data in coordinator.data[AZD_SYSTEMS].items():
        for zone_id, zone_data in system_data[AZD_ZONES].items():
            zone_name = zone_data[AZD_NAME]

            device_info: DeviceInfo = {
                "identifiers": {(DOMAIN, f"{system_id},{zone_id}")},
                "manufacturer": MANUFACTURER,
                "name": f"Airzone [{system_id}:{zone_id}] {zone_name}",
            }

            for description in SENSOR_TYPES:
                if description.key in zone_data:
                    sensors.append(
                        AirzoneSensor(
                            coordinator,
                            description,
                            device_info,
                            system_id,
                            zone_id,
                            zone_name,
                        )
                    )

    async_add_entities(sensors, False)


class AirzoneSensor(CoordinatorEntity, SensorEntity):
    """Define an Airzone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
        system_id: int,
        zone_id: int,
        zone_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_name = f"{zone_name} {description.name}"
        self._attr_unique_id = f"airzone_{system_id}_{zone_id}_{description.key}"
        self.entity_description = description
        self.system_id = system_id
        self.zone_id = zone_id

    @property
    def native_value(self):
        """Return the state."""
        system = self.coordinator.data[AZD_SYSTEMS][self.system_id]
        zone = system[AZD_ZONES][self.zone_id]
        return zone[self.entity_description.key]
