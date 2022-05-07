"""Support for the OpenWeatherMap (OWM) service."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UAAirRaidSirenDataUpdateCoordinator
from .const import ATTRIBUTION, BINARY_SENSOR_TYPES, DEFAULT_NAME, DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    # !!! get name from region name
    name = DEFAULT_NAME  # config_entry.data[CONF_NAME]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[UaAirRaidSirenSensor] = []
    for description in BINARY_SENSOR_TYPES:
        entities.append(
            UaAirRaidSirenSensor(
                name,
                config_entry.unique_id,
                description,
                coordinator,
            )
        )

    async_add_entities(entities)


class UaAirRaidSirenSensor(BinarySensorEntity):
    """Abstract class for an OpenWeatherMap sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        name,
        unique_id,
        description: BinarySensorEntityDescription,
        coordinator: UAAirRaidSirenDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._coordinator = coordinator

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_id}-{description.key}".lower()
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._coordinator.data.get(self.entity_description.key, None)
