"""Support for Home Assistant Updater binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import ATTR_NEWEST_VERSION, ATTR_RELEASE_NOTES, DOMAIN as UPDATER_DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the updater binary sensors."""
    if discovery_info is None:
        return

    async_add_entities([UpdaterBinary(hass.data[UPDATER_DOMAIN])])


class UpdaterBinary(BinarySensorEntity):
    """Representation of an updater binary sensor."""

    def __init__(self, coordinator):
        """Initialize the binary sensor."""
        self.coordinator = coordinator

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
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        if not self.coordinator.data:
            return None
        data = {}
        if self.coordinator.data.release_notes:
            data[ATTR_RELEASE_NOTES] = self.coordinator.data.release_notes
        if self.coordinator.data.newest_version:
            data[ATTR_NEWEST_VERSION] = self.coordinator.data.newest_version
        return data

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
