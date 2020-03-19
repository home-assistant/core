"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    POWERWALL_SITE_NAME,
    SITE_INFO_GRID_CODE,
    SITE_INFO_NOMINAL_SYSTEM_ENERGY_KWH,
    SITE_INFO_UTILITY,
)


class PowerWallEntity(Entity):
    """Base class for powerwall entities."""

    def __init__(self, coordinator, site_info):
        """Initialize the sensor."""
        super().__init__()
        self._coordinator = coordinator
        self._site_info = site_info
        # This group of properties will be unique to to the site
        unique_group = (
            site_info[SITE_INFO_UTILITY],
            site_info[SITE_INFO_GRID_CODE],
            str(site_info[SITE_INFO_NOMINAL_SYSTEM_ENERGY_KWH]),
        )
        self.base_unique_id = "_".join(unique_group)

    @property
    def device_info(self):
        """Powerwall device info."""
        return {
            "identifiers": {(DOMAIN, self.base_unique_id)},
            "name": self._site_info[POWERWALL_SITE_NAME],
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)
