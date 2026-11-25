"""Data update coordinator for the Ablago integration."""

from collections.abc import Mapping
from typing import Any, override

from ablago import (
    AblagoAuthError,
    AblagoClient,
    AblagoConnectionError,
    AblagoError,
    AblagoSSLError,
    Zaehlerstand,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type AblagoConfigEntry = ConfigEntry[AblagoCounterCoordinator]


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> AblagoClient:
    """Create a client that uses the shared Home Assistant session."""
    verify_ssl: bool = data[CONF_VERIFY_SSL]
    return AblagoClient(
        data[CONF_URL],
        data[CONF_API_KEY],
        session=async_get_clientsession(hass, verify_ssl),
        verify_ssl=verify_ssl,
    )


class AblagoCounterCoordinator(DataUpdateCoordinator[Zaehlerstand]):
    """Fetch the counters of the person the API key belongs to."""

    config_entry: AblagoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AblagoConfigEntry, client: AblagoClient
    ) -> None:
        """Initialize the counter coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="Ablago counters",
            update_interval=UPDATE_INTERVAL,
        )
        # Keeps the ETag, so unchanged counters cost a 304 without a body.
        self.client = client

    @override
    async def _async_update_data(self) -> Zaehlerstand:
        """Fetch the counters."""
        try:
            return await self.client.zaehler()
        except AblagoAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except AblagoSSLError as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN, translation_key="ssl_error"
            ) from err
        except AblagoConnectionError as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except AblagoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="unexpected_response"
            ) from err
