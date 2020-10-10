"""Base class for all Subaru Entities."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, ICONS, VEHICLE_NAME, VEHICLE_VIN


class SubaruEntity(CoordinatorEntity):
    """Representation of a Subaru Entity."""

    def __init__(self, vehicle_info, coordinator):
        """Initialize the Subaru Entity."""
        super().__init__(coordinator)
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
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": self.car_name,
            "manufacturer": DOMAIN,
        }
