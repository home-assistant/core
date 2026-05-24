"""DataUpdateCoordinators for HDFury Integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_INFO: Final = timedelta(seconds=60)
SCAN_INTERVAL_CONFIG: Final = timedelta(seconds=60)


class HDFuryInfoCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator for HDFury device info (signal routing, port selections)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HDFuryAPI
    ) -> None:
        """Initialize the info coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="HDFury Info",
            update_interval=SCAN_INTERVAL_INFO,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch device info."""
        try:
            return await self.client.get_info()
        except HDFuryError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error


class HDFuryConfigCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator for HDFury device config (switches, numbers)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HDFuryAPI
    ) -> None:
        """Initialize the config coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="HDFury Config",
            update_interval=SCAN_INTERVAL_CONFIG,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch device configuration."""
        try:
            return await self.client.get_config()
        except HDFuryError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error


@dataclass(kw_only=True)
class HDFuryRuntimeData:
    """Runtime data for HDFury integration."""

    client: HDFuryAPI
    host: str
    board: dict[str, str]
    info_coordinator: HDFuryInfoCoordinator
    config_coordinator: HDFuryConfigCoordinator


type HDFuryConfigEntry = ConfigEntry[HDFuryRuntimeData]


async def async_create_runtime_data(
    hass: HomeAssistant, entry: HDFuryConfigEntry
) -> HDFuryRuntimeData:
    """Create runtime data with coordinators."""
    host: str = entry.data[CONF_HOST]
    client = HDFuryAPI(host, async_get_clientsession(hass))

    try:
        board = await client.get_board()
    except HDFuryError as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
        ) from error

    info_coordinator = HDFuryInfoCoordinator(hass, entry, client)
    config_coordinator = HDFuryConfigCoordinator(hass, entry, client)

    await info_coordinator.async_config_entry_first_refresh()
    await config_coordinator.async_config_entry_first_refresh()

    return HDFuryRuntimeData(
        client=client,
        host=host,
        board=board,
        info_coordinator=info_coordinator,
        config_coordinator=config_coordinator,
    )
