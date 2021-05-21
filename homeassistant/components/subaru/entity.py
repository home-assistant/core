"""Base class for all Subaru Entities."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, VEHICLE_NAME, VEHICLE_VIN


class SubaruEntity(CoordinatorEntity):
    """Representation of a Subaru Entity."""

    def __init__(self, vehicle_info, coordinator):
        """Initialize the Subaru Entity."""
        super().__init__(coordinator)
        self.car_name = vehicle_info[VEHICLE_NAME]
        self.vin = vehicle_info[VEHICLE_VIN]
        self.entity_type = "entity"

    @property
    def name(self):
        """Return name."""
        return f"{self.car_name} {self.entity_type}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.vin}_{self.entity_type}"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": self.car_name,
            "manufacturer": MANUFACTURER,
        }
