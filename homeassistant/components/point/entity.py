"""Support for Minut Point."""

import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import as_local, parse_datetime, utc_from_timestamp

from .const import DOMAIN, SIGNAL_UPDATE_ENTITY

_LOGGER = logging.getLogger(__name__)


class MinutPointEntity(Entity):
    """Base Entity used by the sensors."""

    _attr_should_poll = False

    def __init__(self, point_client, device_id, device_class) -> None:
        """Initialize the entity."""
        self._async_unsub_dispatcher_connect = None
        self._client = point_client
        self._id = device_id
        self._name = self.device.name
        self._attr_device_class = device_class
        self._updated = utc_from_timestamp(0)
        self._attr_unique_id = f"point.{device_id}-{device_class}"
        device = self.device.device
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device["device_mac"])},
            identifiers={(DOMAIN, device["device_id"])},
            manufacturer="Minut",
            model=f"Point v{device['hardware_version']}",
            name=device["description"],
            sw_version=device["firmware"]["installed"],
            via_device=(DOMAIN, device["home"]),
        )
        if device_class:
            self._attr_name = f"{self._name} {device_class.capitalize()}"

    def __str__(self) -> str:
        """Return string representation of device."""
        return f"MinutPoint {self.name}"

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.debug("Created device %s", self)
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback
        )
        await self._update_callback()

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def _update_callback(self):
        """Update the value of the sensor."""

    @property
    def available(self):
        """Return true if device is not offline."""
        return self._client.is_available(self.device_id)

    @property
    def device(self):
        """Return the representation of the device."""
        return self._client.device(self.device_id)

    @property
    def device_id(self):
        """Return the id of the device."""
        return self._id

    @property
    def extra_state_attributes(self):
        """Return status of device."""
        attrs = self.device.device_status
        attrs["last_heard_from"] = as_local(self.last_update).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return attrs

    @property
    def is_updated(self):
        """Return true if sensor have been updated."""
        return self.last_update > self._updated

    @property
    def last_update(self):
        """Return the last_update time for the device."""
        return parse_datetime(self.device.last_update)
