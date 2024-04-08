"""Support for monitoring pyLoad."""

from __future__ import annotations

from enum import StrEnum
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PyLoadCoordinator

_LOGGER = logging.getLogger(__name__)


class PyLoadBinarySensorEntity(StrEnum):
    """PyLoad Status Sensor Entities."""

    DOWNLOAD = "download"
    CAPTCHA = "captcha"


SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    PyLoadBinarySensorEntity.DOWNLOAD: BinarySensorEntityDescription(
        key=PyLoadBinarySensorEntity.DOWNLOAD,
        translation_key=PyLoadBinarySensorEntity.DOWNLOAD,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
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
        self._attr_unique_id = f"{entry.data[CONF_URL]}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name="PyLoad",
            manufacturer="PyLoad Team",
            configuration_url=entry.data[CONF_URL],
            identifiers={(DOMAIN, entry.data[CONF_URL])},
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.coordinator.data[self.entity_description.key]
