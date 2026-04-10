"""Base entity for the WiiM integration."""

from __future__ import annotations

from wiim.wiim_device import WiimDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class WiimBaseEntity(Entity):
    """Base representation of a WiiM entity."""

    _attr_has_entity_name = True

    def __init__(self, wiim_device: WiimDevice) -> None:
        """Initialize the WiiM base entity."""
        self._device = wiim_device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, self._device.udn)},
            name=self._device.name,
            manufacturer=self._device.manufacturer,
            model=self._device.model_name,
            sw_version=self._device.firmware_version,
        )
        if self._device.presentation_url:
            self._attr_device_info["configuration_url"] = self._device.presentation_url
        elif self._device.http_api_url:
            self._attr_device_info["configuration_url"] = self._device.http_api_url

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.available
