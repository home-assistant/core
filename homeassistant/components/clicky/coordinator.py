"""Coordinator to handle Clicky API access."""

import asyncio
import logging
from typing import Any, override

from aiohttp import ClientError
from pyclicky import AuthenticationError, ClickyAPIError, ClickyClient, ConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, REQUEST_TIMEOUT, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ClickyConfigEntry = ConfigEntry[ClickyCoordinator]


class ClickyCoordinator(DataUpdateCoordinator):
    """Handle fetching Clicky data and updating sensors."""

    config_entry: ClickyConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ClickyConfigEntry, client: ClickyClient
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.client = client

    @override
    async def _async_update_data(
        self,
    ) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT), self.client:
                visitors_online = await self.client.visitors_online()
                time_total = await self.client.time_total()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from error
        except ClientError:
            # pyclicky passes the sitekey as a query parameter and does not wrap
            # aiohttp errors, whose messages can include the request URL. Drop
            # the chain so the sitekey doesn't end up in logged tracebacks.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from None
        except (ConnectionError, TimeoutError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from error
        except ClickyAPIError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from error

        return {
            "visitorsOnline": visitors_online.value
            if visitors_online.value is not None
            else 0,
            "timeTotal": time_total.value if time_total.value is not None else 0,
        }
