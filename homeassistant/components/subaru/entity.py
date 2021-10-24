"""Base class for all Subaru Entities."""
from homeassistant.helpers.entity import DeviceInfo
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle_info[VEHICLE_VIN])},
            manufacturer=MANUFACTURER,
            name=vehicle_info[VEHICLE_NAME],
        )

    @property
    def name(self):
        """Return name."""
        return f"{self.car_name} {self.entity_type}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.vin}_{self.entity_type}"
