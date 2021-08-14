"""Support for UPnP/IGD Binary Sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
<<<<<<< HEAD
=======
from homeassistant.helpers import device_registry as dr
>>>>>>> Updates based on review
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import DOMAIN, LOGGER, WANSTATUS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    LOGGER.debug("Adding binary sensor")

    sensors = [
        UpnpStatusBinarySensor(coordinator),
    ]
    async_add_entities(sensors)


class UpnpStatusBinarySensor(UpnpEntity, BinarySensorEntity):
    """Class for UPnP/IGD binary sensors."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
<<<<<<< HEAD
        self._attr_name = f"{coordinator.device.name} wan status"
        self._attr_unique_id = f"{coordinator.device.udn}_wanstatus"
=======
        self._device = device
        self._attr_name = f"{device.name} wan status"
        self._attr_unique_id = f"{device.udn}_wanstatus"
        self._attr_device_info = {
            "connections": {(dr.CONNECTION_UPNP, device.udn)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model_name,
        }

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"
>>>>>>> Updates based on review

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.get(WANSTATUS)

    @property
<<<<<<< HEAD
    def is_on(self) -> bool:
=======
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def is_on(self):
>>>>>>> Updates based on review
        """Return true if the binary sensor is on."""
        return self.coordinator.data[WANSTATUS] == "Connected"
