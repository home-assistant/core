"""
Support for Wink locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.wink/
"""
import asyncio
import logging
from os import path

import voluptuous as vol

from homeassistant.components.lock import LockDevice
from homeassistant.components.wink import WinkDevice, DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, ATTR_CODE
from homeassistant.config import load_yaml_config_file

DEPENDENCIES = ['wink']

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_VACATION_MODE = 'wink_set_lock_vacation_mode'
SERVICE_SET_ALARM_MODE = 'wink_set_lock_alarm_mode'
SERVICE_SET_ALARM_SENSITIVITY = 'wink_set_lock_alarm_sensitivity'
SERVICE_SET_ALARM_STATE = 'wink_set_lock_alarm_state'
SERVICE_SET_BEEPER_STATE = 'wink_set_lock_beeper_state'
SERVICE_ADD_KEY = 'wink_add_new_lock_key_code'

ATTR_ENABLED = 'enabled'
ATTR_SENSITIVITY = 'sensitivity'
ATTR_MODE = 'mode'
ATTR_NAME = 'name'

ALARM_SENSITIVITY_MAP = {"low": 0.2, "medium_low": 0.4,
                         "medium": 0.6, "medium_high": 0.8,
                         "high": 1.0}

ALARM_MODES_MAP = {"tamper": "tamper",
                   "activity": "alert",
                   "forced_entry": "forced_entry"}

SET_ENABLED_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_ENABLED): cv.string,
})

SET_SENSITIVITY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_SENSITIVITY): vol.In(ALARM_SENSITIVITY_MAP)
})

SET_ALARM_MODES_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_MODE): vol.In(ALARM_MODES_MAP)
})

ADD_KEY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_CODE): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    for lock in pywink.get_locks():
        _id = lock.object_id() + lock.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkLockDevice(lock, hass)])

    def service_handle(service):
        """Handler for services."""
        entity_ids = service.data.get('entity_id')
        all_locks = hass.data[DOMAIN]['entities']['lock']
        locks_to_set = []
        if entity_ids is None:
            locks_to_set = all_locks
        else:
            for lock in all_locks:
                if lock.entity_id in entity_ids:
                    locks_to_set.append(lock)

        for lock in locks_to_set:
            if service.service == SERVICE_SET_VACATION_MODE:
                lock.set_vacation_mode(service.data.get(ATTR_ENABLED))
            elif service.service == SERVICE_SET_ALARM_STATE:
                lock.set_alarm_state(service.data.get(ATTR_ENABLED))
            elif service.service == SERVICE_SET_BEEPER_STATE:
                lock.set_beeper_state(service.data.get(ATTR_ENABLED))
            elif service.service == SERVICE_SET_ALARM_MODE:
                lock.set_alarm_mode(service.data.get(ATTR_MODE))
            elif service.service == SERVICE_SET_ALARM_SENSITIVITY:
                lock.set_alarm_sensitivity(service.data.get(ATTR_SENSITIVITY))
            elif service.service == SERVICE_ADD_KEY:
                name = service.data.get(ATTR_NAME)
                code = service.data.get(ATTR_CODE)
                lock.add_new_key(code, name)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_SET_VACATION_MODE,
                           service_handle,
                           descriptions.get(SERVICE_SET_VACATION_MODE),
                           schema=SET_ENABLED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_ALARM_STATE,
                           service_handle,
                           descriptions.get(SERVICE_SET_ALARM_STATE),
                           schema=SET_ENABLED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_BEEPER_STATE,
                           service_handle,
                           descriptions.get(SERVICE_SET_BEEPER_STATE),
                           schema=SET_ENABLED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_ALARM_MODE,
                           service_handle,
                           descriptions.get(SERVICE_SET_ALARM_MODE),
                           schema=SET_ALARM_MODES_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_ALARM_SENSITIVITY,
                           service_handle,
                           descriptions.get(SERVICE_SET_ALARM_SENSITIVITY),
                           schema=SET_SENSITIVITY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_ADD_KEY,
                           service_handle,
                           descriptions.get(SERVICE_ADD_KEY),
                           schema=ADD_KEY_SCHEMA)


class WinkLockDevice(WinkDevice, LockDevice):
    """Representation of a Wink lock."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['lock'].append(self)

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self.wink.state()

    def lock(self, **kwargs):
        """Lock the device."""
        self.wink.set_state(True)

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.wink.set_state(False)

    def set_alarm_state(self, enabled):
        """Set lock's alarm state."""
        self.wink.set_alarm_state(enabled)

    def set_vacation_mode(self, enabled):
        """Set lock's vacation mode."""
        self.wink.set_vacation_mode(enabled)

    def set_beeper_state(self, enabled):
        """Set lock's beeper mode."""
        self.wink.set_beeper_mode(enabled)

    def add_new_key(self, code, name):
        """Add a new user key code."""
        self.wink.add_new_key(code, name)

    def set_alarm_sensitivity(self, sensitivity):
        """
        Set lock's alarm sensitivity.

        Valid sensitivities:
            0.2, 0.4, 0.6, 0.8, 1.0
        """
        self.wink.set_alarm_sensitivity(sensitivity)

    def set_alarm_mode(self, mode):
        """
        Set lock's alarm mode.

        Valid modes:
            alert - Beep when lock is locked or unlocked
            tamper - 15 sec alarm when lock is disturbed when locked
            forced_entry - 3 min alarm when significant force applied
                           to door when locked.
        """
        self.wink.set_alarm_mode(mode)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        super_attrs = super().device_state_attributes
        sensitivity = dict_value_to_key(ALARM_SENSITIVITY_MAP,
                                        self.wink.alarm_sensitivity())
        super_attrs['alarm_sensitivity'] = sensitivity
        super_attrs['vacation_mode'] = self.wink.vacation_mode_enabled()
        super_attrs['beeper_mode'] = self.wink.beeper_enabled()
        super_attrs['auto_lock'] = self.wink.auto_lock_enabled()
        alarm_mode = dict_value_to_key(ALARM_MODES_MAP,
                                       self.wink.alarm_mode())
        super_attrs['alarm_mode'] = alarm_mode
        super_attrs['alarm_enabled'] = self.wink.alarm_enabled()
        return super_attrs


def dict_value_to_key(dict_map, comp_value):
    """Return the key that has the provided value."""
    for key, value in dict_map.items():
        if value == comp_value:
            return key
    return STATE_UNKNOWN
