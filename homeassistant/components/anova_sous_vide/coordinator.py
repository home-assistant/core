"""Support for Anova Sous Vide Coordinators."""
from datetime import timedelta
import logging

from anova_wifi import AnovaOffline, AnovaPrecisionCooker
import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AnovaCoordinator(DataUpdateCoordinator):
    """Anova custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        anova_api: AnovaPrecisionCooker,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            name="Anova Precision Cooker",
            logger=_LOGGER,
            update_interval=timedelta(seconds=30),
        )
        assert self.config_entry is not None
        self._device_id = self.config_entry.data["device_id"]
        self.anova_api = anova_api
        self.device_info: DeviceInfo | None = None

    @callback
    def async_setup(self, firmware_version: str) -> None:
        """Set the firmware version info."""
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
            sw_version=firmware_version,
        )

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self.anova_api.update(self._device_id)
        except AnovaOffline as err:
            raise UpdateFailed(err) from err
