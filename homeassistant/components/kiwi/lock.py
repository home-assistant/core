"""Support for the KIWI.KI lock platform."""
import logging

from kiwiki import KiwiClient, KiwiException
import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, LockEntity
from homeassistant.const import (
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

ATTR_TYPE = "hardware_type"
ATTR_PERMISSION = "permission"
ATTR_CAN_INVITE = "can_invite_others"

UNLOCK_MAINTAIN_TIME = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the KIWI lock platform."""

    try:
        kiwi = KiwiClient(config[CONF_USERNAME], config[CONF_PASSWORD])
    except KiwiException as exc:
        _LOGGER.error(exc)
        return
    available_locks = kiwi.get_locks()
    if not available_locks:
        # No locks found; abort setup routine.
        _LOGGER.info("No KIWI locks found in your account")
        return
    add_entities([KiwiLock(lock, kiwi) for lock in available_locks], True)


class KiwiLock(LockEntity):
    """Representation of a Kiwi lock."""

    def __init__(self, kiwi_lock, client):
        """Initialize the lock."""
        self._sensor = kiwi_lock
        self._client = client
        self.lock_id = kiwi_lock["sensor_id"]
        self._state = STATE_LOCKED

        address = kiwi_lock.get("address")
        address.update(
            {
                ATTR_LATITUDE: address.pop("lat", None),
                ATTR_LONGITUDE: address.pop("lng", None),
            }
        )

        self._device_attrs = {
            ATTR_ID: self.lock_id,
            ATTR_TYPE: kiwi_lock.get("hardware_type"),
            ATTR_PERMISSION: kiwi_lock.get("highest_permission"),
            ATTR_CAN_INVITE: kiwi_lock.get("can_invite"),
            **address,
        }

    @property
    def name(self):
        """Return the name of the lock."""
        name = self._sensor.get("name")
        specifier = self._sensor["address"].get("specifier")
        return name or specifier

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return self._device_attrs

    @callback
    def clear_unlock_state(self, _):
        """Clear unlock state automatically."""
        self._state = STATE_LOCKED
        self.async_write_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""

        try:
            self._client.open_door(self.lock_id)
        except KiwiException:
            _LOGGER.error("failed to open door")
        else:
            self._state = STATE_UNLOCKED
            self.hass.add_job(
                async_call_later,
                self.hass,
                UNLOCK_MAINTAIN_TIME,
                self.clear_unlock_state,
            )
