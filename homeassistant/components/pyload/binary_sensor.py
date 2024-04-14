"""Support for monitoring pyLoad."""

from __future__ import annotations

from enum import StrEnum
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import PyLoadCoordinator
from .util import api_url

_LOGGER = logging.getLogger(__name__)


class PyLoadBinarySensorEntity(StrEnum):
    """PyLoad Status Sensor Entities."""

    CAPTCHA = "captcha"


SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    PyLoadBinarySensorEntity.CAPTCHA: BinarySensorEntityDescription(
        key=PyLoadBinarySensorEntity.CAPTCHA,
        translation_key=PyLoadBinarySensorEntity.CAPTCHA,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        PyLoadBinarySensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS.values()
    )


class PyLoadBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True
    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: BinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            configuration_url=api_url(entry.data),
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key=DOMAIN,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.coordinator.data[self.entity_description.key]

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
