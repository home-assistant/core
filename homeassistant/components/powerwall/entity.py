"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL


class PowerWallEntity(CoordinatorEntity):
    """Base class for powerwall entities."""

    def __init__(
        self, coordinator, site_info, status, device_type, powerwalls_serial_numbers
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
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
