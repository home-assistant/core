"""DataUpdateCoordinator for NRGkick integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from nrgkick_api import (
    NRGkickAPI,
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
    NRGkickInvalidResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Type alias for typed config entry with runtime_data.
type NRGkickConfigEntry = ConfigEntry[NRGkickDataUpdateCoordinator]


@dataclass(slots=True)
class NRGkickData:
    """Container for coordinator data."""

    info: dict[str, Any]
    control: dict[str, Any]
    values: dict[str, Any]


class NRGkickDataUpdateCoordinator(DataUpdateCoordinator[NRGkickData]):
    """Class to manage fetching NRGkick data from the API."""

    config_entry: NRGkickConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: NRGkickAPI, entry: NRGkickConfigEntry
    ) -> None:
        """Initialize."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
            always_update=False,
        )

    async def _async_update_data(self) -> NRGkickData:
        """Update data via library."""
        try:
            info = await self.api.get_info(raw=True)
            control = await self.api.get_control()
            values = await self.api.get_values(raw=True)
        except NRGkickAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NRGkickAPIDisabledError as error:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="json_api_disabled",
            ) from error
        except NRGkickConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error
        except NRGkickInvalidResponseError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error
        except (TimeoutError, aiohttp.ClientError, OSError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

        return NRGkickData(info=info, control=control, values=values)
