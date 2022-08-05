"""Update coordinator for HomeWizard."""
from __future__ import annotations

import logging

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.components.repairs import IssueSeverity, async_create_issue
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_NAME, DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy

    def __init__(self, hass: HomeAssistant, host: str, entity_name: str) -> None:
        """Initialize Update Coordinator."""

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = HomeWizardEnergy(host, clientsession=async_get_clientsession(hass))
        self.name = entity_name

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
            raise UpdateFailed("Device did not respond as expected") from ex

        except DisabledError as ex:
            async_create_issue(
                self.hass,
                DOMAIN,
                f"api_disabled_{self.config_entry.entry_id if self.config_entry is not None else ''}",
                data={CONF_IP_ADDRESS: self.api.host, CONF_DEVICE_NAME: self.name},
                is_fixable=True,
                learn_more_url="https://www.home-assistant.io/integrations/homewizard/#enable-the-api",
                severity=IssueSeverity.ERROR,
                translation_key="api_disabled",
                translation_placeholders={
                    "device_name": self.name,
                },
            )
            raise UpdateFailed("API disabled, API must be enabled in the app") from ex

        return data
