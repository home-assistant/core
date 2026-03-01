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
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_TOKEN, CONF_SSL, CONF_SSL_VERIFY, DOMAIN, POLL_INTERVAL

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
            port=config_entry.data[CONF_PORT],
            token=config_entry.data[CONF_API_TOKEN],
            ssl=config_entry.data.get(CONF_SSL, False),
            verify=config_entry.data.get(CONF_SSL_VERIFY, False),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> KioskerData:
        """Update data via library."""
        try:
            status = await self.hass.async_add_executor_job(self.api.status)
            blackout = await self.hass.async_add_executor_job(self.api.blackout_get)
            screensaver = await self.hass.async_add_executor_job(
                self.api.screensaver_get_state
            )
        except (AuthenticationError, IPAuthenticationError) as exc:
            _LOGGER.error("Authentication failed: %s", exc)
            raise ConfigEntryAuthFailed("Authentication failed") from exc
        except (ConnectionError, PingError) as exc:
            _LOGGER.debug("Connection failed: %s", exc)
            raise UpdateFailed(f"Connection failed: {exc}") from exc
        except TLSVerificationError as exc:
            _LOGGER.debug("TLS verification failed: %s", exc)
            raise UpdateFailed(f"TLS verification failed: {exc}") from exc
        except BadRequestError as exc:
            _LOGGER.warning("Bad request to Kiosker API: %s", exc)
            raise UpdateFailed(f"Bad request: {exc}") from exc
        except (OSError, TimeoutError) as exc:
            _LOGGER.debug("Connection timeout or OS error: %s", exc)
            raise UpdateFailed(f"Connection timeout: {exc}") from exc
        except Exception as exc:
            _LOGGER.exception("Unexpected error updating Kiosker data")
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

        return KioskerData(
            status=status,
            blackout=blackout,
            screensaver=screensaver,
        )
