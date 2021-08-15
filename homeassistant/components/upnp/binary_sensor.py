"""Support for UPnP/IGD Binary Sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import DOMAIN, LOGGER, UPTIME, WANIP, WANSTATUS


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
        self._attr_name = f"{coordinator.device.name} wan status"
        self._attr_unique_id = f"{coordinator.device.udn}_wanstatus"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._coordinator.data.get(WANSTATUS)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._coordinator.data[WANSTATUS] == "Connected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        if self._coordinator.data[WANSTATUS] is not None:
            attributes.update({"WAN Status": self._coordinator.data[WANSTATUS]})
        if self._coordinator.data[WANIP] is not None:
            attributes.update({"WAN IP": self._coordinator.data[WANIP]})
        if self._coordinator.data[UPTIME] is not None:
            attributes.update({"Uptime": self._coordinator.data[UPTIME]})

        return attributes
