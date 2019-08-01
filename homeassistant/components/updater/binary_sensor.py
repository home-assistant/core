"""Support for Home Assistant Updater binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import ATTR_NEWEST_VERSION, ATTR_RELEASE_NOTES, DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the updater binary sensors."""
    updater = hass.data[DOMAIN]

    async_add_entities([UpdaterBinary(updater)])


class UpdaterBinary(BinarySensorDevice):
    """Representation of an updater binary sensor."""

    def __init__(self, updater):
        """Initialize the binary sensor."""
        self._updater = updater

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
        return "on" if self._updater.update_available else "off"

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return "connectivity"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True if self._updater.update_available is not None else False

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    @property
    def device_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        data = super().device_state_attributes
        if data is None:
            data = {}
        if self._updater.release_notes:
            data[ATTR_RELEASE_NOTES] = self._updater.release_notes
        if self._updater.newest_version:
            data[ATTR_NEWEST_VERSION] = self._updater.newest_version
        return data
