"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.entity import DeviceInfo
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
    def device_info(self) -> DeviceInfo:
        """Powerwall device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=f"{MODEL} ({self._device_type.name})",
            name=self._site_info.site_name,
            sw_version=self._version,
        )
