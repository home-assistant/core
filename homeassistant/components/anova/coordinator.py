"""Support for Anova Coordinators."""
from datetime import timedelta
import logging

from anova_wifi import AnovaOffline, AnovaPrecisionCooker, APCUpdate
import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate]):
    """Anova custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        anova_device: AnovaPrecisionCooker,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            name="Anova Precision Cooker",
            logger=_LOGGER,
            update_interval=timedelta(seconds=30),
        )
        assert self.config_entry is not None
        self._device_unique_id = anova_device.device_key
        self.anova_device = anova_device
        self.device_info: DeviceInfo | None = None

    @callback
    def async_setup(self, firmware_version: str) -> None:
        """Set the firmware version info."""
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_unique_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
            sw_version=firmware_version,
        )

    async def _async_update_data(self) -> APCUpdate:
        try:
            async with async_timeout.timeout(5):
                return await self.anova_device.update()
        except AnovaOffline as err:
            raise UpdateFailed(err) from err
