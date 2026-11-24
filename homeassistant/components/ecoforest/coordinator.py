"""The ecoforest coordinator."""

import logging
from typing import override

from pyecoforest.api import EcoforestApi
from pyecoforest.exceptions import EcoforestAuthenticationRequired, EcoforestError
from pyecoforest.models.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)

type EcoforestConfigEntry = ConfigEntry[EcoforestCoordinator]


class EcoforestCoordinator(DataUpdateCoordinator[Device]):
    """DataUpdateCoordinator to gather data from ecoforest device."""

    config_entry: EcoforestConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: EcoforestConfigEntry, api: EcoforestApi
    ) -> None:
        """Initialize DataUpdateCoordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="ecoforest",
            update_interval=POLLING_INTERVAL,
        )
        self.api = api

    @override
    async def _async_update_data(self) -> Device:
        """Fetch all device and sensor data from api."""
        try:
            data = await self.api.get()
        except EcoforestAuthenticationRequired as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={"host": self.config_entry.data[CONF_HOST]},
            ) from err
        except EcoforestError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        _LOGGER.debug("Ecoforest data: %s", data)
        return data
