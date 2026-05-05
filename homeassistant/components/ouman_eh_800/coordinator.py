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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type OumanEh800ConfigEntry = ConfigEntry[OumanEh800Coordinator]


class OumanEh800Coordinator(DataUpdateCoordinator[dict[OumanEndpoint, OumanValues]]):
    """Ouman EH-800 data update coordinator."""

    _registry_set: OumanRegistrySet

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: OumanEh800Client,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ouman EH-800",
            config_entry=config_entry,
            update_interval=update_interval,
            always_update=False,
        )
        self.client: OumanEh800Client = client

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
