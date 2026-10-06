"""DataUpdateCoordinator for Fumis."""

from typing import override

from fumis import (
    Fumis,
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisInfo,
    FumisStoveOfflineError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.signal_type import SignalTypeFormat

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type FumisConfigEntry = ConfigEntry[FumisDataUpdateCoordinator]

# Keyed by config entry ID, so automation triggers keep listening when the
# entry reloads and a new coordinator takes over.
SIGNAL_COORDINATOR_UPDATED: SignalTypeFormat[FumisDataUpdateCoordinator] = (
    SignalTypeFormat(f"{DOMAIN}_{{}}_coordinator_updated")
)


class FumisDataUpdateCoordinator(DataUpdateCoordinator[FumisInfo]):
    """Class to manage fetching Fumis data."""

    config_entry: FumisConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FumisConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = Fumis(
            mac=entry.data[CONF_MAC],
            password=entry.data[CONF_PIN],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.unique_id}",
            update_interval=SCAN_INTERVAL,
        )

    @override
    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners and notify the automation triggers."""
        super().async_update_listeners()
        async_dispatcher_send(
            self.hass,
            SIGNAL_COORDINATOR_UPDATED.format(self.config_entry.entry_id),
            self,
        )

    @override
    async def _async_update_data(self) -> FumisInfo:
        """Fetch data from the Fumis API."""
        try:
            return await self.client.update_info()
        except FumisAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except FumisStoveOfflineError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="stove_offline",
            ) from err
        except FumisConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except FumisError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
