"""Support for KEBA charging station switch."""
import logging

from homeassistant.components.lock import LockDevice

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba = hass.data[DOMAIN]

    sensors = [
        KebaLock('Authentication', keba)
    ]
    async_add_entities(sensors)


class KebaLock(LockDevice):
    """The entity class for KEBA charging stations switch."""

    def __init__(self, name, keba):
        """Initialize the KEBA switch."""
        self._keba = keba
        self._name = name
        self._state = None
        self._attributes = {
            'rfid_tag': self._keba.rfid
        }

    def open(self, **kwargs):
        """Open the door latch."""
        return

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return f"{self._keba.device_name}_{self._name}"

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        if self._state is None:
            return True
        return self._state

    async def async_lock(self, **kwargs):
        """Lock wallbox."""
        await self._keba.async_stop()

    async def async_unlock(self, **kwargs):
        """Unlock wallbox."""
        await self._keba.async_start()

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
