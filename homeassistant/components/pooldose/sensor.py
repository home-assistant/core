"""The Seko Pooldose API Sensors."""

from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SENSOR_MAP
from .coordinator import PooldoseCoordinator
from .pooldose_api import PooldoseAPIClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose sensors from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    for uid, (name, unit, device_class, key) in SENSOR_MAP.items():
        entities.append(
            PooldoseSensor(coordinator, api, name, uid, key, unit, device_class)
        )
    async_add_entities(entities)


class PooldoseSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for Seko Pooldose API."""

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        api: PooldoseAPIClient,
        name: str,
        uid: str,
        key: str,
        unit: str | None,
        device_class: str | None,
    ) -> None:
        """Initialize a PooldoseSensor entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_name = name
        self._attr_unique_id = uid
        self._key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = cast(SensorDeviceClass | None, device_class)

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][
                self._key
            ]["current"]
        except (KeyError, TypeError):
            return None
        return value
