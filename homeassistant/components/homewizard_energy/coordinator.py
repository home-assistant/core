"""Update coordinator for HomeWizard Energy."""

from datetime import timedelta
import logging

import aiohwenergy
import async_timeout

from homeassistant.const import CONF_API_VERSION, CONF_ID, CONF_NAME, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_POWER_ON,
    ATTR_SWITCHLOCK,
    CONF_DATA,
    CONF_MODEL,
    CONF_SW_VERSION,
    MODEL_P1,
)

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the energy device."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: aiohwenergy.HomeWizardEnergy,
    ) -> None:
        """Initialize Update Coordinator."""

        self.api = api

        update_interval = self.get_update_interval()
        super().__init__(hass, _LOGGER, name="", update_interval=update_interval)

    def get_update_interval(self) -> timedelta:
        """Return best interval for product type."""
        try:
            product_type = self.api.device.product_type
        except AttributeError:
            product_type = "Unknown"

        if product_type == MODEL_P1:
            try:
                smr_version = self.api.data.smr_version
                if smr_version == 50:
                    return timedelta(seconds=1)

            except AttributeError:
                pass

        return timedelta(seconds=5)

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""
        try:
            async with async_timeout.timeout(10):
                # Update all properties
                status = await self.api.update()

                if not status:
                    raise Exception("Failed to fetch data")

                data = {
                    CONF_NAME: self.api.device.product_name,
                    CONF_MODEL: self.api.device.product_type,
                    CONF_ID: self.api.device.serial,
                    CONF_SW_VERSION: self.api.device.firmware_version,
                    CONF_API_VERSION: self.api.device.api_version,
                    CONF_DATA: {},
                    CONF_STATE: None,
                }

                for datapoint in self.api.data.available_datapoints:
                    data[CONF_DATA][datapoint] = getattr(self.api.data, datapoint)

                if self.api.state is not None:
                    data[CONF_STATE] = {
                        ATTR_POWER_ON: self.api.state.power_on,
                        ATTR_SWITCHLOCK: self.api.state.switch_lock,
                        ATTR_BRIGHTNESS: self.api.state.brightness,
                    }

        except Exception as ex:
            raise UpdateFailed(ex) from ex

        self.name = data[CONF_NAME]
        return data
