"""Update coordinator for HomeWizard Energy."""

import logging

import aiohwenergy
import async_timeout

from homeassistant.const import CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_POWER_ON,
    ATTR_SWITCHLOCK,
    CONF_DATA,
    CONF_DEVICE,
    UPDATE_INTERVAL,
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
        super().__init__(hass, _LOGGER, name="", update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""

        async with async_timeout.timeout(10):
            # Update all properties
            status = await self.api.update()

            if not status:
                raise UpdateFailed("Failed to communicate with device")

            data = {
                CONF_DEVICE: self.api.device,
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

        # self.name = data[CONF_NAME]
        return data
