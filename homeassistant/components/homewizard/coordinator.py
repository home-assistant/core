"""Update coordinator for HomeWizard."""
from __future__ import annotations

from datetime import timedelta
import logging

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)

MAX_UPDATE_INTERVAL = timedelta(minutes=30)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy
    api_disabled: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = HomeWizardEnergy(host, clientsession=async_get_clientsession(hass))

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""

        # Update all properties
        try:
            data: DeviceResponseEntry = {
                "device": await self.api.device(),
                "data": await self.api.data(),
                "state": await self.api.state(),
            }

        except RequestError as ex:
            raise UpdateFailed(ex) from ex

        except DisabledError as ex:
            if not self.api_disabled and self.config_entry:
                self.api_disabled = True
                self.config_entry.async_start_reauth(self.hass)

            # Exponentially increase update interval
            if (
                self.update_interval is not None
                and self.update_interval < MAX_UPDATE_INTERVAL
            ):
                self.update_interval = self.update_interval * 2
            raise UpdateFailed(ex) from ex

        else:
            if self.api_disabled:
                self.api_disabled = False
                self.update_interval = UPDATE_INTERVAL

        return data
