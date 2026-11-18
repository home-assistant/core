"""Coordinator for Genius Hub System."""

import logging
import traceback
from typing import override

import aiohttp
from geniushubclient import GeniusHub
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

type GeniusHubConfigEntry = ConfigEntry[GeniusCoordinator]

_LOGGER = logging.getLogger(__name__)


class GeniusCoordinator(DataUpdateCoordinator):
    """Container for geniushub client and data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: GeniusHub,
        entry: GeniusHubConfigEntry,
        hub_uid: str,
    ) -> None:
        """Initialize the geniushub client."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.hass = hass
        self.client = client
        self.hub_uid = hub_uid

    @override
    async def _async_update_data(self) -> GeniusHub:
        """Update the geniushub client's data."""
        try:
            await self.client.update()

        except (
            aiohttp.ClientResponseError,
            aiohttp.ClientConnectorError,
        ) as api_err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_communicating_with_api",
                translation_placeholders={
                    "api_err": str(api_err),
                },
            ) from api_err
        except aiohttp.ClientPayloadError as api_err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_communicating_with_api",
                translation_placeholders={
                    "api_err": str(api_err),
                },
            ) from api_err
        except (TimeoutError, requests.exceptions.Timeout) as timeout_err:
            err_traceback = traceback.format_exc()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_communicating_with_api",
                translation_placeholders={
                    "err_traceback": err_traceback,
                },
            ) from timeout_err

        self.make_debug_log_entries()

        return self.client

    def make_debug_log_entries(self) -> None:
        """Make any useful debug log entries."""
        _LOGGER.debug(
            "Raw JSON: \n\nclient._zones = %s \n\nclient._devices = %s",
            self.client._zones,  # noqa: SLF001
            self.client._devices,  # noqa: SLF001
        )
