"""
Support for the KIWI.KI lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.kiwi/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, ATTR_ID, ATTR_LONGITUDE, ATTR_LATITUDE)

REQUIREMENTS = ['kiwiki-client==0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_TYPE = 'hardware_type'
ATTR_PERMISSION = 'permission'
ATTR_CAN_INVITE = 'can_invite_others'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KIWI lock platform."""
    from kiwiki import KiwiClient
    kiwi = KiwiClient(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    add_devices([KiwiLock(lock, kiwi) for lock in kiwi.get_locks()], True)


class KiwiLock(LockDevice):
    """Representation of a Kiwi lock."""

    def __init__(self, kiwi_lock, client):
        """Initialize the lock."""
        self._sensor = kiwi_lock
        self._device_attrs = None
        self._client = client
        self.lock_id = kiwi_lock['sensor_id']

        address = kiwi_lock.get('address')
        lat = address.pop('lat', None)
        lng = address.pop('lng', None)

        self._device_attrs = {
            ATTR_ID: self.lock_id,
            ATTR_TYPE: kiwi_lock.get('hardware_type'),
            ATTR_PERMISSION: kiwi_lock.get('highest_permission'),
            ATTR_CAN_INVITE: kiwi_lock.get('can_invite')}

        self._device_attrs.update(address)
        self._device_attrs.update({
            ATTR_LATITUDE: lat,
            ATTR_LONGITUDE: lng
        })

    @property
    def name(self):
        """Return the name of the lock."""
        name = self._sensor.get('name')
        specifier = self._sensor['address'].get('specifier')
        return name or specifier

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return True

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return self._device_attrs

    def unlock(self, **kwargs):
        """Unlock the device."""
        from kiwiki import KiwiException
        try:
            self._client.open_door(self.lock_id)
        except KiwiException:
            _LOGGER.error("failed to open door")
