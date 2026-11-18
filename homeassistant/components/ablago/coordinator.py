"""Data update coordinators for the Ablago integration."""

from dataclasses import dataclass
from typing import override

from ablago import (
    AblagoAuthError,
    AblagoClient,
    AblagoConnectionError,
    AblagoError,
    AblagoSSLError,
    Gesundheit,
    Zaehlerstand,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_COUNTERS, UPDATE_INTERVAL_HEALTH

type AblagoConfigEntry = ConfigEntry[AblagoData]


@dataclass
class AblagoData:
    """Runtime data of one config entry (one person in one Ablago)."""

    counters: AblagoCounterCoordinator
    health: AblagoHealthCoordinator


def create_client(hass: HomeAssistant, data: dict[str, object]) -> AblagoClient:
    """Create a client that uses the shared Home Assistant session."""
    verify_ssl = bool(data.get(CONF_VERIFY_SSL, True))
    return AblagoClient(
        str(data[CONF_URL]),
        str(data[CONF_API_KEY]),
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
            update_interval=UPDATE_INTERVAL_COUNTERS,
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
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="ssl_error"
            ) from err
        except AblagoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except AblagoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="unexpected_response"
            ) from err


class AblagoHealthCoordinator(DataUpdateCoordinator[Gesundheit | None]):
    """Check whether Ablago is running.

    Never fails: an unreachable Ablago is the information here, so it becomes ``None`` (shown as disconnected)
    instead of an unavailable entity.
    """

    config_entry: AblagoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AblagoConfigEntry, client: AblagoClient
    ) -> None:
        """Initialize the health coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="Ablago health",
            update_interval=UPDATE_INTERVAL_HEALTH,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> Gesundheit | None:
        """Fetch the health state."""
        try:
            return await self.client.gesundheit()
        except AblagoError as err:
            LOGGER.debug("Ablago is not reachable: %s", err)
            return None
