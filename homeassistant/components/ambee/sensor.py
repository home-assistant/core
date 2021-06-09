"""Support for Ambee sensors."""
from __future__ import annotations

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    ATTR_SERVICE,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ambee sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AmbeeSensor(coordinator=coordinator, entry_id=entry.entry_id, key=sensor)
        for sensor in SENSORS
    )


class AmbeeSensor(CoordinatorEntity, SensorEntity):
    """Defines an Ambee sensor."""

    def __init__(
        self, *, coordinator: DataUpdateCoordinator, entry_id: str, key: str
    ) -> None:
        """Initialize Ambee sensor."""
        super().__init__(coordinator=coordinator)
        self._key = key
        self._entry_id = entry_id
        self._service_key, self._service_name = SENSORS[key][ATTR_SERVICE]

        self._attr_device_class = SENSORS[key].get(ATTR_DEVICE_CLASS)
        self._attr_name = SENSORS[key][ATTR_NAME]
        self._attr_state_class = SENSORS[key].get(ATTR_STATE_CLASS)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_unit_of_measurement = SENSORS[key].get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, self._key)  # type: ignore[no-any-return]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Ambee Service."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, f"{self._entry_id}_{self._service_key}")},
            ATTR_NAME: self._service_name,
            ATTR_MANUFACTURER: "Ambee",
        }
