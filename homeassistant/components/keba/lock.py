"""Support for KEBA charging station switch."""
import logging

from homeassistant.components.lock import LockDevice

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    _LOGGER.debug("Initializing KEBA charging station lock")
    sensors = []
    sensors.append(KebaLock('Authentication', hass))
    async_add_entities(sensors)


class KebaLock(LockDevice):
    """The entity class for KEBA charging stations switch."""

    def __init__(self, key, hass):
        """Initialize the KEBA switch."""
        self._keba = hass.data[DOMAIN]
        self._key = key
        self._state = None
        self._hass = hass
        self._attributes = {}
        self._attributes['RFID tag'] = self._keba.rfid

    @property
    def should_poll(self):
        """"Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return "keba_" + self._key

    @property
    def name(self):
        """Return the name of the device."""
        return "keba_" + self._key

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes.items()

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        if self._state is None:
            return True
        return self._state

    def lock(self, **kwargs):
        """Lock wallbox."""
        self._hass.async_create_task(self._keba.async_stop())

    def unlock(self, **kwargs):
        """Unlock wallbox."""
        self._hass.async_create_task(self._keba.async_start())

    async def async_update(self):
        """Attempt to retrieve on off state from the switch."""
        self._state = self._keba.get_value('Authreq') == 1

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._keba.add_update_listener(self.update_callback)
