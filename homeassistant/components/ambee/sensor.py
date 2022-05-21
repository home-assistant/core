"""Support for Ambee sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSORS, SERVICES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ambee sensors based on a config entry."""
    async_add_entities(
        AmbeeSensorEntity(
            coordinator=hass.data[DOMAIN][entry.entry_id][service_key],
            entry_id=entry.entry_id,
            description=description,
            service_key=service_key,
            service=SERVICES[service_key],
        )
        for service_key, service_sensors in SENSORS.items()
        for description in service_sensors
    )


class AmbeeSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines an Ambee sensor."""

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
        service_key: str,
        service: str,
    ) -> None:
        """Initialize Ambee sensor."""
        super().__init__(coordinator=coordinator)
        self._service_key = service_key

        self.entity_id = f"{SENSOR_DOMAIN}.{service_key}_{description.key}"
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{service_key}_{description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{service_key}")},
            manufacturer="Ambee",
            name=service,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = getattr(self.coordinator.data, self.entity_description.key)
        if isinstance(value, str):
            return value.lower()
        return value  # type: ignore[no-any-return]
