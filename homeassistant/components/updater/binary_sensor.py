"""Support for Home Assistant Updater binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ATTR_NEWEST_VERSION, ATTR_RELEASE_NOTES, DISPATCHER_REMOTE_UPDATE, Updater


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the updater binary sensors."""
    async_add_entities([UpdaterBinary()])


class UpdaterBinary(BinarySensorDevice):
    """Representation of an updater binary sensor."""

    def __init__(self):
        """Initialize the binary sensor."""
        self._update_available = None
        self._release_notes = None
        self._newest_version = None
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the binary sensor, if any."""
        return "Updater"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "updater"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._update_available

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._update_available is not None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        data = super().device_state_attributes
        if data is None:
            data = {}
        if self._release_notes:
            data[ATTR_RELEASE_NOTES] = self._release_notes
        if self._newest_version:
            data[ATTR_NEWEST_VERSION] = self._newest_version
        return data

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        @callback
        def async_state_update(updater: Updater):
            """Update callback."""
            self._newest_version = updater.newest_version
            self._release_notes = updater.release_notes
            self._update_available = updater.update_available
            self.async_schedule_update_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DISPATCHER_REMOTE_UPDATE, async_state_update
        )

    async def async_will_remove_from_hass(self):
        """Register update dispatcher."""
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
