"""Base class for Nanoleaf entity."""

from aionanoleaf import Nanoleaf

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class NanoleafEntity(CoordinatorEntity):
    """Representation of a Nanoleaf entity."""

    def __init__(self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator) -> None:
        """Initialize an Nanoleaf entity."""
        super().__init__(coordinator)
        self._nanoleaf = nanoleaf
        self._available = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, nanoleaf.serial_no)},
            manufacturer=nanoleaf.manufacturer,
            model=nanoleaf.model,
            name=nanoleaf.name,
            sw_version=nanoleaf.firmware_version,
            configuration_url=f"http://{nanoleaf.host}",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._available = self.coordinator.last_update_success
        self.async_write_ha_state()

    @callback
    def async_set_available(self) -> None:
        """Set available to True."""
        self._available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._nanoleaf.serial_no}_set_available",
                self.async_set_available,
            )
        )
