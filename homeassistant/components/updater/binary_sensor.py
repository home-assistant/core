"""Support for Home Assistant Updater binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ATTR_NEWEST_VERSION, ATTR_RELEASE_NOTES, DOMAIN as UPDATER_DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the updater binary sensors."""
    if discovery_info is None:
        return

    async_add_entities([UpdaterBinary(hass.data[UPDATER_DOMAIN])])


class UpdaterBinary(CoordinatorEntity, BinarySensorEntity):
    """Representation of an updater binary sensor."""

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
        if not self.coordinator.data:
            return None
        return self.coordinator.data.update_available

    @property
    def extra_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        if not self.coordinator.data:
            return None
        data = {}
        if self.coordinator.data.release_notes:
            data[ATTR_RELEASE_NOTES] = self.coordinator.data.release_notes
        if self.coordinator.data.newest_version:
            data[ATTR_NEWEST_VERSION] = self.coordinator.data.newest_version
        return data
