"""Data update coordinator for the gridX integration."""

from typing import Any, override

from gridx_connector import (
    AsyncGridboxConnector,
    GridXAuthenticationError,
    GridXError,
    GridXSystem,
    build_login_config,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, HTTP_TIMEOUT, LIVE_UPDATE_INTERVAL, LOGGER

type GridxConfigEntry = ConfigEntry[GridxLiveCoordinator]


def create_connector(
    hass: HomeAssistant, username: str, password: str
) -> AsyncGridboxConnector:
    """Create a connector that uses Home Assistant's shared httpx client."""
    return AsyncGridboxConnector(
        build_login_config(username, password),
        logger=LOGGER,
        httpx_client=get_async_client(hass),
        timeout=HTTP_TIMEOUT,
    )


class GridxLiveCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch the live snapshot of every system, keyed by system id."""

    config_entry: GridxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: GridxConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=LIVE_UPDATE_INTERVAL,
        )
        self.connector = create_connector(
            hass, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )

    @property
    def systems(self) -> dict[str, GridXSystem]:
        """Return the systems discovered for the account."""
        return self.connector.systems

    @override
    async def _async_setup(self) -> None:
        """Authenticate and discover the systems of the account."""
        try:
            await self.connector.initialize()
        except GridXAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except GridXError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch live data for all systems; fail if any system fails."""
        try:
            return await self.connector.get_live_data()
        except GridXAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except GridXError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
