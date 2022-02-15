"""Update coordinator for HomeWizard."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TypedDict

from homewizard_energy.errors import DisabledError
from homewizard_energy.homewizard_energy import HomeWizardEnergy
from homewizard_energy.models import Data, Device, State

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SERVICE_DATA, SERVICE_DEVICE, SERVICE_STATE

_LOGGER = logging.getLogger(__name__)


class HomeWizardEnergyData(TypedDict):
    """Class for defining data in dict."""

    device: Device
    data: Data
    state: State | None


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[HomeWizardEnergyData]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5)
        )
        self.api = HomeWizardEnergy(host, clientsession=async_get_clientsession(hass))

    async def _async_update_data(self) -> HomeWizardEnergyData:
        """Fetch all device and sensor data from api."""

        try:
            data: HomeWizardEnergyData = {
                SERVICE_DEVICE: await self.api.device(),
                SERVICE_DATA: await self.api.data(),
                SERVICE_STATE: await self.api.state(),
            }
        except DisabledError as error:
            raise UpdateFailed(error) from error

        return data
