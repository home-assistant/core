"""Update coordinator for HomeWizard."""

from __future__ import annotations

from homewizard_energy import HomeWizardEnergy, HomeWizardEnergyV1
from homewizard_energy.errors import DisabledError, RequestError
from homewizard_energy.models import CombinedModels as DeviceResponseEntry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy
    api_disabled: bool = False

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = HomeWizardEnergyV1(
            self.config_entry.data[CONF_IP_ADDRESS],
            clientsession=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""
        try:
            data = await self.api.combined()

        except RequestError as ex:
            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="communication_error"
            ) from ex

        except DisabledError as ex:
            if not self.api_disabled:
                self.api_disabled = True

                # Do not reload when performing first refresh
                if self.data is not None:
                    # Reload config entry to let init flow handle retrying and trigger repair flow
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="api_disabled"
            ) from ex

        self.api_disabled = False

        self.data = data
        return data
