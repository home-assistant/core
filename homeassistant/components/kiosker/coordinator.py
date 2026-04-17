"""DataUpdateCoordinator for Kiosker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from kiosker import (
    AuthenticationError,
    BadRequestError,
    Blackout,
    ConnectionError,
    IPAuthenticationError,
    KioskerAPI,
    PingError,
    ScreensaverState,
    Status,
    TLSVerificationError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_TOKEN, DOMAIN, POLL_INTERVAL, PORT

_LOGGER = logging.getLogger(__name__)

type KioskerConfigEntry = ConfigEntry[KioskerDataUpdateCoordinator]


@dataclass
class KioskerData:
    """Data structure for Kiosker integration."""

    status: Status
    blackout: Blackout | None
    screensaver: ScreensaverState | None


class KioskerDataUpdateCoordinator(DataUpdateCoordinator[KioskerData]):
    """Class to manage fetching data from the Kiosker API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KioskerConfigEntry,
    ) -> None:
        """Initialize."""
        self.api = KioskerAPI(
            host=config_entry.data[CONF_HOST],
            port=PORT,
            token=config_entry.data[CONF_API_TOKEN],
            ssl=config_entry.data.get(CONF_SSL, False),
            verify=config_entry.data.get(CONF_VERIFY_SSL, False),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )

    def _fetch_all_data(self) -> tuple[Status, Blackout, ScreensaverState]:
        """Fetch all data from the API in a single executor job."""
        status = self.api.status()
        blackout = self.api.blackout_get()
        screensaver = self.api.screensaver_get_state()
        return status, blackout, screensaver

    async def _async_update_data(self) -> KioskerData:
        """Update data via library."""
        try:
            status, blackout, screensaver = await self.hass.async_add_executor_job(
                self._fetch_all_data
            )
        except AuthenticationError as exc:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Check your API token."
            ) from exc
        except IPAuthenticationError as exc:
            raise ConfigEntryAuthFailed(
                "IP authentication failed. Check your IP whitelist."
            ) from exc
        except (ConnectionError, PingError) as exc:
            raise UpdateFailed(f"Connection failed: {exc}") from exc
        except TLSVerificationError as exc:
            raise UpdateFailed(f"TLS verification failed: {exc}") from exc
        except BadRequestError as exc:
            raise UpdateFailed(f"Bad request: {exc}") from exc
        except (OSError, TimeoutError) as exc:
            raise UpdateFailed(f"Connection timeout: {exc}") from exc
        except Exception as exc:
            _LOGGER.exception("Unexpected error updating Kiosker data")
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

        return KioskerData(
            status=status,
            blackout=blackout,
            screensaver=screensaver,
        )
