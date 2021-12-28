"""Update coordinator for HomeWizard."""
from __future__ import annotations

import asyncio
import logging

import aiohwenergy
import async_timeout

from homeassistant.const import CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DATA, CONF_DEVICE, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the energy device."""

    api: aiohwenergy | None = None
    host: str

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.host = host

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""

        async with async_timeout.timeout(10):

            if self.api is None:
                self.api = await self.initialize_api()

            # Update all properties
            try:
                if not await self.api.update():
                    await self._close_api()
                    raise UpdateFailed("Failed to communicate with device")

            except aiohwenergy.DisabledError as ex:
                await self._close_api()

                raise UpdateFailed(
                    "API disabled, API must be enabled in the app"
                ) from ex

            except Exception as ex:  # pylint: disable=broad-except
                await self._close_api()

                raise UpdateFailed(
                    f"Error connecting with Energy Device at {self.host}"
                ) from ex

            data = {
                CONF_DEVICE: self.api.device,
                CONF_DATA: {},
                CONF_STATE: None,
            }

            for datapoint in self.api.data.available_datapoints:
                data[CONF_DATA][datapoint] = getattr(self.api.data, datapoint)

        return data

    async def initialize_api(self) -> aiohwenergy:
        """Initialize API and validate connection."""

        api = aiohwenergy.HomeWizardEnergy(self.host)

        try:
            await api.initialize()
            return api

        except (asyncio.TimeoutError, aiohwenergy.RequestError) as ex:
            raise UpdateFailed(
                f"Error connecting to the Energy device at {self.host}"
            ) from ex

        except aiohwenergy.DisabledError as ex:
            raise ex

        except aiohwenergy.AiohwenergyException as ex:
            raise UpdateFailed("Unknown Energy API error occurred") from ex

        except Exception as ex:  # pylint: disable=broad-except
            raise UpdateFailed(
                f"Unknown error connecting with Energy Device at {self.host}"
            ) from ex

    async def _close_api(self) -> None:
        if self.api is not None:
            await self.api.close()
            self.api = None
