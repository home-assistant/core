"""Support for Vera devices."""

from __future__ import annotations

import logging
from typing import Any

import pyvera as veraApi

from homeassistant.const import (
    ATTR_ARMED,
    ATTR_BATTERY_LEVEL,
    ATTR_LAST_TRIP_TIME,
    ATTR_TRIPPED,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.dt import utc_from_timestamp

from .common import ControllerData
from .const import CONF_LEGACY_UNIQUE_ID, VERA_ID_FORMAT

_LOGGER = logging.getLogger(__name__)


class VeraEntity[_DeviceTypeT: veraApi.VeraDevice](Entity):
    """Representation of a Vera device entity."""

    def __init__(
        self, vera_device: _DeviceTypeT, controller_data: ControllerData
    ) -> None:
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller_data.controller

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.vera_device_id
        )

        if controller_data.config_entry.data.get(CONF_LEGACY_UNIQUE_ID):
            self._unique_id = str(self.vera_device.vera_device_id)
        else:
            self._unique_id = f"vera_{controller_data.config_entry.unique_id}_{self.vera_device.vera_device_id}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.controller.register(self.vera_device, self._update_callback)

    def _update_callback(self, _device: _DeviceTypeT) -> None:
        """Update the state."""
        self.schedule_update_ha_state(True)

    def update(self):
        """Force a refresh from the device if the device is unavailable."""
        refresh_needed = self.vera_device.should_poll or not self.available
        _LOGGER.debug("%s: update called (refresh=%s)", self._name, refresh_needed)
        if refresh_needed:
            self.vera_device.refresh()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = "True" if armed else "False"

        if self.vera_device.is_trippable:
            if (last_tripped := self.vera_device.last_trip) is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = "True" if tripped else "False"

        attr["Vera Device Id"] = self.vera_device.vera_device_id

        return attr

    @property
    def available(self):
        """If device communications have failed return false."""
        return not self.vera_device.comm_failure

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return self._unique_id
