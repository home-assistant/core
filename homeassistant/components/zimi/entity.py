"""Base Platform for zimi integrations."""

from __future__ import annotations

import logging

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZimiEntity(Entity):
    """Representation of a Zimi API device."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiDevice."""

        self._attr_unique_id = (
            device.identifier
        )  # device characteristic ID - unique from ZCC
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.identifier)},
            name=self._device.name.strip(),
            manufacturer=api.brand,
            model=self._device.type,
            suggested_area=self._device.room,
            via_device=(DOMAIN, api.mac),
        )

        _LOGGER.debug(
            "Initialising ZimiDevice %s in %s", self._device.name, self._device.room
        )

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._device.is_connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to the events."""
        await super().async_added_to_hass()
        self._device.subscribe(self)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup ZimiLight with removal of notification prior to removal."""
        self._device.unsubscribe(self)
        await super().async_will_remove_from_hass()

    def notify(self, _observable: object):
        """Receive notification from device that state has changed.

        No data is fetched for the notification but schedule_update_ha_state is called.
        """

        _LOGGER.debug(
            "Received notification() for %s in %s", self._device.name, self._device.room
        )
        self.schedule_update_ha_state(force_refresh=True)
