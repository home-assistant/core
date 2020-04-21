"""Base class for wiffi entities."""

from datetime import datetime, timedelta

from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class WiffiEntity(Entity):
    """Common functionality for all wiffi entities."""

    def __init__(self, device, metric):
        """Initialize the base elements of a wiffi entity."""
        self._id = f"{device.mac_address.replace(':', '')}-{metric.name}"
        self._device_info = {
            "connections": {
                (device_registry.CONNECTION_NETWORK_MAC, device.mac_address)
            },
            "identifiers": {(DOMAIN, device.mac_address)},
            "manufacturer": "stall.biz",
            "name": f"{device.moduletype} {device.mac_address}",
            "model": device.moduletype,
            "sw_version": device.sw_version,
        }
        self._name = metric.description
        self._expiration_date = None
        self._value = None

    @property
    def should_poll(self):
        """Disable polling because data driven ."""
        return False

    @property
    def device_info(self):
        """Return wiffi device info which is shared between all entities of a device."""
        return self._device_info

    @property
    def unique_id(self):
        """Return unique id for entity."""
        return self._id

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def available(self):
        """Return true if value is valid."""
        return self._value is not None

    def reset_expiration_date(self):
        """Reset value expiration date.

        Will be called by derived classes after a value update has been received.
        """
        self._expiration_date = datetime.now() + timedelta(minutes=3)

    @callback
    def async_check_expiration_date(self):
        """Periodically check if entity value has been updated.

        If there are no more updates from the wiffi device, the value will be
        set to unavailable.
        """
        if (
            self._value is not None
            and self._expiration_date is not None
            and datetime.now() > self._expiration_date
        ):
            self._value = None
            self.async_write_ha_state()
