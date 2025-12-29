"""DataUpdateCoordinator for ntfy integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiontfy import Account as NtfyAccount, Ntfy
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyHTTPError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type NtfyConfigEntry = ConfigEntry[NtfyDataUpdateCoordinator]


class NtfyDataUpdateCoordinator(DataUpdateCoordinator[NtfyAccount]):
    """Ntfy data update coordinator."""

    config_entry: NtfyConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: NtfyConfigEntry, ntfy: Ntfy
    ) -> None:
        """Initialize the ntfy data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

        self.ntfy = ntfy

    async def _async_update_data(self) -> NtfyAccount:
        """Fetch account data from ntfy."""

        try:
            return await self.ntfy.account()
        except NtfyUnauthorizedAuthenticationError as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e
        except NtfyHTTPError as e:
            _LOGGER.debug("Error %s: %s [%s]", e.code, e.error, e.link)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error_msg": str(e.error)},
            ) from e
        except NtfyConnectionError as e:
            _LOGGER.debug("Error", exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from e
        except NtfyTimeoutError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from e
