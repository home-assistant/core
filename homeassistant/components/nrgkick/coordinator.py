"""DataUpdateCoordinator for NRGkick integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NRGkickAPI,
    NRGkickApiClientApiDisabledError,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
)
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
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
            # Data is a dict that supports __eq__ comparison.
            # Avoid unnecessary entity updates when data hasn't changed.
            always_update=False,
        )

    async def _async_update_data(self) -> NRGkickData:
        """Update data via library."""
        try:
            info = await self.api.get_info()
            control = await self.api.get_control()
            values = await self.api.get_values()
        except NRGkickApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except NRGkickApiClientApiDisabledError as err:
            raise UpdateFailed(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err
        except NRGkickApiClientCommunicationError as err:
            raise UpdateFailed(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err

        return NRGkickData(info=info, control=control, values=values)
