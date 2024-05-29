# REVIEWED

# pylint: disable=fixme

"""Code to handle a Hue bridge."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

import aiohttp
from aiohttp import ClientSession
from aiohue import HueBridgeV2
from aiohue.errors import AiohueException
from came_domotic_unofficial import Auth, CameDomoticAPI
from came_domotic_unofficial.errors import (
    CameDomoticAuthError,
    CameDomoticServerError,
    CameDomoticServerNotFoundError,
)
from came_domotic_unofficial.models import CameServerInfo

from homeassistant import core
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .v2.device import async_setup_devices
from .v2.hue_event import async_setup_hue_events

# How long should we sleep if the hub is busy

PLATFORMS = [
    Platform.LIGHT,
]


class CameDomoticServer:
    """Manages a single CAME Domotic server."""

    # TODO Sanitize
    def __init__(self, hass: core.HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.logger = logging.getLogger(__name__)
        self.websession: ClientSession | None = None
        # store actual api connection to CAME server as api
        self.api_came: CameDomoticAPI | None = None
        self.server_info: CameServerInfo | None = None
        self.mac_address: str | None = None

        # store (this) server object in hass data
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

        # Jobs to be executed when API is reset.
        self.reset_jobs: list[core.CALLBACK_TYPE] = []

        # TODO remove
        self.api = HueBridgeV2("self.host - without quotes", "app_key - without quotes")

    @property  # TODO remove
    def api_version(self) -> int:
        """Return api version we're set-up for."""
        return 2

    # TODO sanitize
    async def async_initialize_api(self) -> bool:
        """Initialize CAME Domotic API instance."""
        setup_ok = False
        try:
            conf_host: str = self.config_entry.data[CONF_HOST]
            conf_username: str = self.config_entry.data[CONF_USERNAME]
            conf_password: str = self.config_entry.data[CONF_PASSWORD]

            self.websession = aiohttp_client.async_get_clientsession(self.hass)
            async with asyncio.timeout(20):
                auth: Auth = await Auth.async_create(
                    self.websession, conf_host, conf_username, conf_password
                )
                self.api_came = CameDomoticAPI(auth)
                self.server_info = await self.api_came.async_get_server_info()

            self.mac_address = format_mac(self.server_info.keycode)

            setup_ok = True
        except (CameDomoticServerNotFoundError, CameDomoticAuthError) as err:
            # The server host can be moved or the credentials can be changed.
            # We are going to fail the config entry setup and initiate a new
            # linking procedure. When linking succeeds, it will remove the
            # old config entry.
            self.logger.warning(
                "Error connecting to the CAME Domotic server at %s: %s."
                "Starting a new config flow.",
                conf_host,
                err,
            )
            create_config_flow(self.hass, conf_host, conf_username, conf_password)
            return False
        except CameDomoticServerError as err:
            raise ConfigEntryError(
                f"Bad response from the CAME Domotic server: {err}"
            ) from err
        except Exception:
            self.logger.exception("Unknown error connecting to CAME Domotic server.")
            return False
        finally:
            if not setup_ok and self.websession is not None:
                await self.websession.close()

        await async_setup_devices(self)  # TODO sanitize
        await async_setup_hue_events(self)  # TODO sanitize
        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

        # add listener for config entry updates.
        self.reset_jobs.append(self.config_entry.add_update_listener(_update_listener))
        return True

    # TODO sanitize
    async def async_request_call(self, task: Callable, *args, **kwargs) -> Any:
        """Send request to the Hue bridge."""
        try:
            return await task(*args, **kwargs)
        except AiohueException as err:
            # The (new) Hue api can be a bit fanatic with throwing errors so
            # we have some logic to treat some responses as warning only.
            msg = f"Request failed: {err}"
            if "may not have effect" in str(err):
                # log only
                self.logger.debug(msg)
                return None
            raise HomeAssistantError(msg) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"Request failed due connection error: {err}"
            ) from err

    async def async_reset(self) -> bool:
        """Reset this CAME Domotic API instance to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # The bridge can be in 3 states:
        #  - Setup was successful, self.api is not None
        #  - Authentication was wrong, self.api is None, not retrying setup.

        # If the API instance setup was wrong.
        if self.api_came is None:
            return True

        while self.reset_jobs:
            self.reset_jobs.pop()()

        # Unload platforms
        unload_success = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        if unload_success:
            self.hass.data[DOMAIN].pop(self.config_entry.entry_id)

        return unload_success


async def _update_listener(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Handle ConfigEntry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def create_config_flow(
    hass: core.HomeAssistant, host: str, username: str, password: str
) -> None:
    """Start a config flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"host": host, "username": username, "password": password},
        )
    )
