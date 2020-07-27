"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL


class PowerWallEntity(Entity):
    """Base class for powerwall entities."""

    def __init__(
        self, coordinator, site_info, status, device_type, powerwalls_serial_numbers
    ):
        """Initialize the sensor."""
        super().__init__()
        self._coordinator = coordinator
        self._site_info = site_info
        self._device_type = device_type
        self._version = status.version
        # The serial numbers of the powerwalls are unique to every site
        self.base_unique_id = "_".join(powerwalls_serial_numbers)

    @property
    def device_info(self):
        """Powerwall device info."""
        device_info = {
            "identifiers": {(DOMAIN, self.base_unique_id)},
            "name": self._site_info.site_name,
            "manufacturer": MANUFACTURER,
        }
        model = MODEL
        model += f" ({self._device_type.name})"
        device_info["model"] = model
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
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
