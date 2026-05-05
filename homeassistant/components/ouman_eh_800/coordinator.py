"""Data update coordinator for the Ouman EH-800 integration."""

from datetime import timedelta
import logging

from ouman_eh_800_api import (
    ControllableEndpoint,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
    OumanEh800Client,
    OumanEndpoint,
    OumanRegistrySet,
    OumanValues,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

type OumanEh800ConfigEntry = ConfigEntry[OumanEh800Coordinator]


class OumanEh800Coordinator(DataUpdateCoordinator[dict[OumanEndpoint, OumanValues]]):
    """Ouman EH-800 data update coordinator."""

    _registry_set: OumanRegistrySet

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OumanEh800ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ouman EH-800",
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
            always_update=False,
        )
        self.client: OumanEh800Client = OumanEh800Client(
            session=async_get_clientsession(hass),
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            address=config_entry.data[CONF_URL],
        )

        self.sensor_endpoints: list[OumanEndpoint] = []

    async def _async_setup(self) -> None:
        try:
            # Even though not required to fetch values, perform login once
            # at the start to verify that the credentials are valid.
            await self.client.login()
            self._registry_set = await self.client.get_active_registries()
        except OumanClientAuthenticationError as err:
            raise ConfigEntryError("Invalid credentials") from err
        except OumanClientCommunicationError as err:
            raise ConfigEntryNotReady("Error communicating with API") from err

        # Categorize the endpoints for platforms
        for endpoint in self._registry_set.endpoints:
            if not isinstance(endpoint, ControllableEndpoint):
                self.sensor_endpoints.append(endpoint)

    async def _async_update_data(self) -> dict[OumanEndpoint, OumanValues]:
        """Fetch registry values from the device."""
        try:
            return await self.client.get_values(self._registry_set)
        except OumanClientCommunicationError as err:
            raise UpdateFailed("Error communicating with API") from err
