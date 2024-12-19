"""Base Platform for zimi integrations."""

from __future__ import annotations

import logging

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import ToggleEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZimiEntity(ToggleEntity):
    """Representation of a Zimi API device."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiDevice."""

        self._attr_unique_id = device.identifier
        self._device = device
        self._device.subscribe(self)
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

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup ZimiLight with removal of notification prior to removal."""
        await super().async_will_remove_from_hass()
        self._device.unsubscribe(self)

    def notify(self, _observable):
        """Receive notification from device that state has changed."""

        _LOGGER.debug(
            "Received notification() for %s in %s", self._device.name, self._device.room
        )
        self.schedule_update_ha_state(force_refresh=True)

    def update(self) -> None:
        """Fetch new state data for this device."""
