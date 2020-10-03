"""Base class for all Subaru Entities."""
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN, ICONS, VEHICLE_NAME, VEHICLE_VIN


class SubaruEntity(Entity):
    """Representation of a Subaru Entity."""

    def __init__(self, vehicle_info, coordinator):
        """Initialize the Subaru Entity."""
        self.coordinator = coordinator
        self.car_name = vehicle_info[VEHICLE_NAME]
        self.vin = vehicle_info[VEHICLE_VIN]
        self.title = "entity"

    @property
    def name(self):
        """Return name."""
        return f"{self.car_name} {self.title}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return slugify(f"{DOMAIN} {self.vin} {self.title}")

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self.title)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": self.car_name,
            "manufacturer": DOMAIN,
        }

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the state of the device."""
        await self.coordinator.async_request_refresh()
