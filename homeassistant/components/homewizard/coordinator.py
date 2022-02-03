"""Update coordinator for HomeWizard."""
from __future__ import annotations

import asyncio
import logging

import aiohwenergy
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: aiohwenergy.HomeWizardEnergy

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

        session = async_get_clientsession(hass)
        self.api = aiohwenergy.HomeWizardEnergy(host, clientsession=session)

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""

        async with async_timeout.timeout(10):

            if self.api.device is None:
                await self.initialize_api()

            # Update all properties
            try:
                if not await self.api.update():
                    raise UpdateFailed("Failed to communicate with device")

            except aiohwenergy.DisabledError as ex:
                raise UpdateFailed(
                    "API disabled, API must be enabled in the app"
                ) from ex

            data: DeviceResponseEntry = {
                "device": self.api.device,
                "data": {},
            }

            for datapoint in self.api.data.available_datapoints:
                data["data"][datapoint] = getattr(self.api.data, datapoint)

        return data

    async def initialize_api(self) -> aiohwenergy:
        """Initialize API and validate connection."""

        try:
            await self.api.initialize()

        except (asyncio.TimeoutError, aiohwenergy.RequestError) as ex:
            raise UpdateFailed(
                f"Error connecting to the Energy device at {self.api.host}"
            ) from ex

        except aiohwenergy.DisabledError as ex:
            raise ex

        except aiohwenergy.AiohwenergyException as ex:
            raise UpdateFailed("Unknown Energy API error occurred") from ex

        except Exception as ex:
            raise UpdateFailed(
                f"Unknown error connecting with Energy Device at {self.api.host}"
            ) from ex
