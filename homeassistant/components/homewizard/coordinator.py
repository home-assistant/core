"""Update coordinator for HomeWizard."""
from __future__ import annotations

from datetime import timedelta
import logging

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
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
        entry_id: str,
        host: str,
    ) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry_id = entry_id
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
            raise UpdateFailed(ex) from ex

        except DisabledError as ex:
            if not self.api_disabled:
                self.api_disabled = True

                # Do not reload when performing first refresh
                if self.data is not None:
                    await self.hass.config_entries.async_reload(self.entry_id)

            raise UpdateFailed(ex) from ex

        else:
            self.api_disabled = False

        return data
