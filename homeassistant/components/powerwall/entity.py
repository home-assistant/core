"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.entity import Entity

from .const import (
    DEVICE_TYPE_DEVICE_TYPE,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    POWERWALL_SITE_NAME,
    SITE_INFO_GRID_CODE,
    SITE_INFO_NOMINAL_SYSTEM_ENERGY_KWH,
    SITE_INFO_UTILITY,
    STATUS_VERSION,
)


class PowerWallEntity(Entity):
    """Base class for powerwall entities."""

    def __init__(self, coordinator, site_info, status, device_type):
        """Initialize the sensor."""
        super().__init__()
        self._coordinator = coordinator
        self._site_info = site_info
        self._device_type = device_type.get(DEVICE_TYPE_DEVICE_TYPE)
        self._version = status.get(STATUS_VERSION)
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
        device_info = {
            "identifiers": {(DOMAIN, self.base_unique_id)},
            "name": self._site_info[POWERWALL_SITE_NAME],
            "manufacturer": MANUFACTURER,
        }
        model = MODEL
        if self._device_type:
            model += f" ({self._device_type})"
        device_info["model"] = model
        if self._version:
            device_info["sw_version"] = self._version
        return device_info

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
