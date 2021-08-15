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

from . import UpnpEntity
from .const import (
    CONFIG_ENTRY_UDN,
    DOMAIN,
    DOMAIN_DEVICES,
    LOGGER,
    UPTIME,
    WANIP,
    WANSTATUS,
)
from .device import Device


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    udn = config_entry.data[CONFIG_ENTRY_UDN]
    device: Device = hass.data[DOMAIN][DOMAIN_DEVICES][udn]

    LOGGER.debug("Adding binary sensor")

    sensors = [
        UpnpStatusBinarySensor(device),
    ]
    async_add_entities(sensors)


class UpnpStatusBinarySensor(UpnpEntity, BinarySensorEntity):
    """Class for UPnP/IGD binary sensors."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(
        self,
        device: Device,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(device)
        self._attr_name = f"{device.name} wan status"
        self._attr_unique_id = f"{device.udn}_wanstatus"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device.coordinator.data.get(WANSTATUS)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._device.coordinator.data[WANSTATUS] == "Connected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        if self._device.coordinator.data[WANSTATUS] is not None:
            attributes.update({"WAN Status": self._device.coordinator.data[WANSTATUS]})
        if self._device.coordinator.data[WANIP] is not None:
            attributes.update({"WAN IP": self._device.coordinator.data[WANIP]})
        if self._device.coordinator.data[UPTIME] is not None:
            attributes.update({"Uptime": self._device.coordinator.data[UPTIME]})

        return attributes
