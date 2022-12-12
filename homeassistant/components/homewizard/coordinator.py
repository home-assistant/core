"""Update coordinator for HomeWizard."""
from __future__ import annotations

import logging

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = HomeWizardEnergy(host, clientsession=async_get_clientsession(hass))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device_info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.data["device"].serial)},
        )

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""

        # Update all properties
        try:
            data: DeviceResponseEntry = {
                "device": await self.api.device(),
                "data": await self.api.data(),
                "state": await self.api.state(),
                "system": None,
            }

            features = await self.api.features()
            if features.has_system:
                data["system"] = await self.api.system()

        except RequestError as ex:
            raise UpdateFailed("Device did not respond as expected") from ex

        except DisabledError as ex:
            raise UpdateFailed("API disabled, API must be enabled in the app") from ex

        return data
