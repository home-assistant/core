"""Support for tracking the online status of a UPS."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VALUE_ONLINE, APCUPSdData

_LOGGER = logging.getLogger(__name__)
_DESCRIPTION = BinarySensorEntityDescription(
    key="statflag",
    name="UPS Online Status",
    icon="mdi:heart",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an APCUPSd Online Status binary sensor."""
    data_service: APCUPSdData = hass.data[DOMAIN][config_entry.entry_id]

    # Do not create the binary sensor if APCUPSd does not provide STATFLAG field for us
    # to determine the online status.
    if data_service.statflag is None:
        return

    async_add_entities(
        [OnlineStatus(data_service, _DESCRIPTION)],
        update_before_add=True,
    )


class OnlineStatus(BinarySensorEntity):
    """Representation of a UPS online status."""

    def __init__(
        self,
        data_service: APCUPSdData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the APCUPSd binary device."""
        # Set up unique id and device info if serial number is available.
        if (serial_no := data_service.serial_no) is not None:
            self._attr_unique_id = f"{serial_no}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, serial_no)},
                model=data_service.model,
                manufacturer="APC",
                hw_version=data_service.hw_version,
                sw_version=data_service.sw_version,
            )
        self.entity_description = description
        self._data_service = data_service

    def update(self) -> None:
        """Get the status report from APCUPSd and set this entity's state."""
        try:
            self._data_service.update()
        except OSError as ex:
            if self._attr_available:
                self._attr_available = False
                _LOGGER.exception("Got exception while fetching state: %s", ex)
            return

        self._attr_available = True
        key = self.entity_description.key.upper()
        if key not in self._data_service.status:
            self._attr_is_on = None
            return

        self._attr_is_on = int(self._data_service.status[key], 16) & VALUE_ONLINE > 0
