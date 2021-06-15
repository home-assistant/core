"""Support for Ambee sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_ENABLED_BY_DEFAULT,
    ATTR_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_SERVICE,
    SENSORS,
    SERVICES,
)
from .models import AmbeeSensor


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
            sensor_key=sensor_key,
            sensor=sensor,
            service_key=service_key,
            service=SERVICES[service_key],
        )
        for service_key, service_sensors in SENSORS.items()
        for sensor_key, sensor in service_sensors.items()
    )


class AmbeeSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines an Ambee sensor."""

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        sensor_key: str,
        sensor: AmbeeSensor,
        service_key: str,
        service: str,
    ) -> None:
        """Initialize Ambee sensor."""
        super().__init__(coordinator=coordinator)
        self._sensor_key = sensor_key
        self._service_key = service_key

        self.entity_id = f"{SENSOR_DOMAIN}.{service_key}_{sensor_key}"
        self._attr_device_class = sensor.get(ATTR_DEVICE_CLASS)
        self._attr_entity_registry_enabled_default = sensor.get(
            ATTR_ENABLED_BY_DEFAULT, True
        )
        self._attr_icon = sensor.get(ATTR_ICON)
        self._attr_name = sensor.get(ATTR_NAME)
        self._attr_state_class = sensor.get(ATTR_STATE_CLASS)
        self._attr_unique_id = f"{entry_id}_{service_key}_{sensor_key}"
        self._attr_unit_of_measurement = sensor.get(ATTR_UNIT_OF_MEASUREMENT)

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, f"{entry_id}_{service_key}")},
            ATTR_NAME: service,
            ATTR_MANUFACTURER: "Ambee",
            ATTR_ENTRY_TYPE: ENTRY_TYPE_SERVICE,
        }

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        value = getattr(self.coordinator.data, self._sensor_key)
        if isinstance(value, str):
            return value.lower()
        return value  # type: ignore[no-any-return]
