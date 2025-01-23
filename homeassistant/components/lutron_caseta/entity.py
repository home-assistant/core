"""Component for interacting with a Lutron Caseta system."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_SUGGESTED_AREA
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONFIG_URL, DOMAIN, MANUFACTURER, UNASSIGNED_AREA
from .models import LutronCasetaData
from .util import area_name_from_id, serial_to_unique_id

_LOGGER = logging.getLogger(__name__)


class LutronCasetaEntity(Entity):
    """Common base class for all Lutron Caseta devices."""

    _attr_should_poll = False

    def __init__(self, device: dict[str, Any], data: LutronCasetaData) -> None:
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        [:param]bridge_device a dict with the details of the bridge
        """
        self._device = device
        self._smartbridge = data.bridge
        self._bridge_device = data.bridge_device
        self._bridge_unique_id = serial_to_unique_id(data.bridge_device["serial"])
        if "serial" not in self._device:
            return

        if "parent_device" in device:
            # This is a child entity, handle the naming in button.py and switch.py
            return
        area = area_name_from_id(self._smartbridge.areas, device["area"])
        name = device["name"].split("_")[-1]
        self._attr_name = full_name = f"{area} {name}"
        info = DeviceInfo(
            # Historically we used the device serial number for the identifier
            # but the serial is usually an integer and a string is expected
            # here. Since it would be a breaking change to change the identifier
            # we are ignoring the type error here until it can be migrated to
            # a string in a future release.
            identifiers={
                (
                    DOMAIN,
                    self._handle_none_serial(self.serial),  # type: ignore[arg-type]
                )
            },
            manufacturer=MANUFACTURER,
            model=f"{device['model']} ({device['type']})",
            name=full_name,
            via_device=(DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
        )
        if area != UNASSIGNED_AREA:
            info[ATTR_SUGGESTED_AREA] = area
        self._attr_device_info = info

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_subscriber(self.device_id, self.async_write_ha_state)

    def _handle_none_serial(self, serial: str | int | None) -> str | int:
        """Handle None serial returned by RA3 and QSX processors."""
        if serial is None:
            return f"{self._bridge_unique_id}_{self.device_id}"
        return serial

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["device_id"]

    @property
    def serial(self) -> int | None:
        """Return the serial number of the device."""
        return self._device["serial"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device (serial)."""
        return str(self._handle_none_serial(self.serial))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "device_id": self.device_id,
        }
        if zone := self._device.get("zone"):
            attributes["zone_id"] = zone
        return attributes


class LutronCasetaUpdatableEntity(LutronCasetaEntity):
    """A lutron_caseta entity that can update by syncing data from the bridge."""

    async def async_update(self) -> None:
        """Update when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)
