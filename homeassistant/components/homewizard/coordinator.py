"""Update coordinator for HomeWizard."""
from __future__ import annotations

import logging

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy
    api_disabled: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry
        self.api = HomeWizardEnergy(host, clientsession=async_get_clientsession(hass))

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""
        try:
            data = DeviceResponseEntry(
                device=await self.api.device(),
                data=await self.api.data(),
                features=await self.api.features(),
                state=await self.api.state(),
            )

            if data.features.has_system:
                data.system = await self.api.system()

        except RequestError as ex:
            raise UpdateFailed(ex) from ex

        except DisabledError as ex:
            if not self.api_disabled:
                self.api_disabled = True

                # Do not reload when performing first refresh
                if self.data is not None:
                    await self.hass.config_entries.async_reload(self.entry.entry_id)

            raise UpdateFailed(ex) from ex

        self.api_disabled = False

        return data
