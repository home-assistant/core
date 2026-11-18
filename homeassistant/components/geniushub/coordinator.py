"""Coordinator for Genius Hub System."""

import logging
import traceback

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
        self._payload_error = False
        self._timeout_error = False
        self._type_error = False

    async def _async_update_data(self) -> GeniusHub | None:
        """Update the geniushub client's data."""
        try:
            await self.client.update()
            self._type_error = False
            if self._payload_error:
                self._payload_error = False
                _LOGGER.info(
                    "Payload error resolved, connection to geniushub re-established"
                )
            if self._timeout_error:
                self._timeout_error = False
                _LOGGER.info(
                    "Timeout error resolved, connection to geniushub re-established"
                )
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
            if not self._payload_error:
                self._payload_error = True
                _LOGGER.info(
                    "Connection to geniushub failed with payload error, message is: %s",
                    api_err,
                )
                return None
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_communicating_with_api",
                translation_placeholders={
                    "api_err": str(api_err),
                },
            ) from api_err
        except (TimeoutError, requests.exceptions.Timeout) as timeout_err:
            err_traceback = traceback.format_exc()
            if not self._timeout_error:
                # _LOGGER.info("Timeout communicating with GH API: %s", err_traceback)
                _LOGGER.info(
                    "Timeout communicating with GH API: %s", self._timeout_error
                )
                self._timeout_error = True
                return None
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
