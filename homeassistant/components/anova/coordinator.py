"""Support for Anova Coordinators."""

import logging

from anova_wifi import APCUpdate, APCWifiDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .models import AnovaConfigEntry

_LOGGER = logging.getLogger(__name__)


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate]):
    """Anova custom coordinator."""

    config_entry: AnovaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnovaConfigEntry,
        anova_device: APCWifiDevice,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name="Anova Precision Cooker",
            logger=_LOGGER,
        )
        self.device_unique_id = anova_device.cooker_id
        self.anova_device = anova_device
        self.anova_device.set_update_listener(self.async_set_updated_data)
        self.device_info: DeviceInfo | None = None

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_unique_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
        )
        self.sensor_data_set: bool = False
