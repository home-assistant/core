"""DateUpdateCoordinator for Kat Bulgaria integration."""

import logging
from typing import Any

import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORD_DATA_KEY, DEFAULT_POLL_INTERVAL, DOMAIN
from .unraid_client import UnraidClient

type UnraidConfigEntry = ConfigEntry[UnraidUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


class UnraidUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    config_entry: UnraidConfigEntry
    client: UnraidClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UnraidConfigEntry,
    ) -> None:
        """Initialize coordinator."""

        unraid_host: str = config_entry.data[CONF_HOST]
        unraid_apikey: str = config_entry.data[CONF_API_KEY]

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"Unraid - {unraid_host}",
            update_interval=DEFAULT_POLL_INTERVAL,
        )

        assert self.config_entry.unique_id
        self.serial_number = self.config_entry.unique_id
        self.client = UnraidClient(hass, unraid_host, unraid_apikey)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            res = await self.client.query_data()

        except httpx.RequestError as e:
            _LOGGER.error("An error occurred while requesting: %s", e)
            return {}
        except httpx.HTTPStatusError as e:
            _LOGGER.error(
                "HTTP error occurred: %s - %s", e.response.status_code, e.response.text
            )
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_config",
            ) from e

        return {COORD_DATA_KEY: res}
