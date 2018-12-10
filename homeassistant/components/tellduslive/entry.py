"""Base Entity for all TelldusLiveEntities."""
from datetime import datetime
import logging

from homeassistant.const import ATTR_BATTERY_LEVEL, DEVICE_DEFAULT_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_UPDATE_ENTITY

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATED = 'time_last_updated'


class TelldusLiveEntity(Entity):
    """Base class for all Telldus Live entities."""

    def __init__(self, client, device_id):
        """Initialize the entity."""
        self._id = device_id
        self._client = client
        self._name = self.device.name
        self._async_unsub_dispatcher_connect = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.debug('Created device %s', self)
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    @callback
    def _update_callback(self):
        """Return the property of the device might have changed."""
        if self.device.name:
            self._name = self.device.name
        self.async_schedule_update_ha_state()

    @property
    def device_id(self):
        """Return the id of the device."""
        return self._id

    @property
    def device(self):
        """Return the representation of the device."""
        return self._client.device(self.device_id)

    @property
    def _state(self):
        """Return the state of the device."""
        return self.device.state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def name(self):
        """Return name of device."""
        return self._name or DEVICE_DEFAULT_NAME

    @property
    def available(self):
        """Return true if device is not offline."""
        return self._client.is_available(self.device_id)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._battery_level:
            attrs[ATTR_BATTERY_LEVEL] = self._battery_level
        if self._last_updated:
            attrs[ATTR_LAST_UPDATED] = self._last_updated
        return attrs

    @property
    def _battery_level(self):
        """Return the battery level of a device."""
        from tellduslive import (BATTERY_LOW,
                                 BATTERY_UNKNOWN,
                                 BATTERY_OK)
        if self.device.battery == BATTERY_LOW:
            return 1
        if self.device.battery == BATTERY_UNKNOWN:
            return None
        if self.device.battery == BATTERY_OK:
            return 100
        return self.device.battery  # Percentage

    @property
    def _last_updated(self):
        """Return the last update of a device."""
        return str(datetime.fromtimestamp(self.device.lastUpdated)) \
            if self.device.lastUpdated else None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._id
