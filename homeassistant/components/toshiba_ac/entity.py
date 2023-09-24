"""Base classes for Toshiba AC entities."""

from __future__ import annotations

import logging

from toshiba_ac.device import ToshibaAcDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ToshibaAcEntity(Entity):
    """Representation of a Toshiba AC device entity."""

    _attr_should_poll = False

    def __init__(self, toshiba_device: ToshibaAcDevice) -> None:
        """Initialize the entity."""
        self._device = toshiba_device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.ac_unique_id)},
            model=self._device.device_id,
            manufacturer="Toshiba",
            name=self._device.name,
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(
            self._device.ac_id
            and self._device.amqp_api.sas_token
            and self._device.http_api.access_token
        )


class ToshibaAcStateEntity(ToshibaAcEntity):
    """Base class for entities that subscribe to the device's state_changed callback."""

    async def async_added_to_hass(self) -> None:
        """Subscribe to the device's state_changed callback."""
        self._device.on_state_changed_callback.add(self._state_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Call when device is removed from HA."""
        self._device.on_state_changed_callback.remove(self._state_changed)

    def update_attrs(self) -> None:
        """Call when the Toshiba AC device state changes."""

    def _state_changed(self, _device: ToshibaAcDevice) -> None:
        """Call when the Toshiba AC device state changes."""
        self.update_attrs()
        self.async_write_ha_state()
