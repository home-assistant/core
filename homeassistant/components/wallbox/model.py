"""Models for Wallbox."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WallboxCoordinator
from .const import (
    CONF_CURRENT_VERSION_KEY,
    CONF_DATA_KEY,
    CONF_NAME_KEY,
    CONF_PART_NUMBER_KEY,
    CONF_SERIAL_NUMBER_KEY,
    CONF_SOFTWARE_KEY,
    DOMAIN,
)


class WallboxEntity(CoordinatorEntity):
    """Defines a base Wallbox entity."""

    coordinator: WallboxCoordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Wallbox device."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.data[CONF_DATA_KEY][CONF_SERIAL_NUMBER_KEY])
            },
            name=f"Wallbox - {self.coordinator.data[CONF_NAME_KEY]}",
            manufacturer="Wallbox",
            model=self.coordinator.data[CONF_DATA_KEY][CONF_PART_NUMBER_KEY],
            sw_version=self.coordinator.data[CONF_DATA_KEY][CONF_SOFTWARE_KEY][
                CONF_CURRENT_VERSION_KEY
            ],
        )
