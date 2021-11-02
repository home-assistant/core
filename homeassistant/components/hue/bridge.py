"""Code to handle a Hue bridge."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import Any, Callable

from aiohttp import client_exceptions
from aiohue import HueBridgeV1, HueBridgeV2, LinkButtonNotPressed, Unauthorized
import async_timeout

from homeassistant import core
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_HUE_SCENES,
    CONF_ALLOW_UNREACHABLE,
    CONF_USE_V2,
    DEFAULT_ALLOW_HUE_GROUPS,
    DEFAULT_ALLOW_HUE_SCENES,
    DEFAULT_ALLOW_UNREACHABLE,
    DOMAIN,
)
from .v1.sensor_base import SensorManager
from .v2.device import async_setup_devices

# How long should we sleep if the hub is busy
HUB_BUSY_SLEEP = 0.5

PLATFORMS_v1 = ["light", "binary_sensor", "sensor"]
PLATFORMS_v2 = ["light", "binary_sensor", "sensor", "scene"]


class HueBridge:
    """Manages a single Hue bridge."""

    def __init__(self, hass: core.HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.available = True
        self.authorized = False
        self.api: HueBridgeV1 | HueBridgeV2 | None = None
        self.parallel_updates_semaphore = asyncio.Semaphore(3)
        # Jobs to be executed when API is reset.
        self.reset_jobs: list[core.CALLBACK_TYPE] = []
        self.sensor_manager: SensorManager | None = None
        self.logger = logging.getLogger(DOMAIN)

    @property
    def host(self) -> str:
        """Return the host of this bridge."""
        return self.config_entry.data[CONF_HOST]

    @property
    def use_v2(self) -> bool:
        """Return bool if we're using the V2 version of the implementation."""
        return self.config_entry.data.get(CONF_USE_V2, False)

    @property
    def allow_unreachable(self) -> bool:
        """Allow unreachable light bulbs."""
        return self.config_entry.options.get(
            CONF_ALLOW_UNREACHABLE, DEFAULT_ALLOW_UNREACHABLE
        )

    @property
    def allow_groups(self) -> bool:
        """Allow groups defined in the Hue bridge."""
        return self.config_entry.options.get(
            CONF_ALLOW_HUE_GROUPS, DEFAULT_ALLOW_HUE_GROUPS
        )

    @property
    def allow_scenes(self) -> bool:
        """Allow scenes defined in the Hue bridge."""
        return self.config_entry.options.get(
            CONF_ALLOW_HUE_SCENES, DEFAULT_ALLOW_HUE_SCENES
        )

    async def async_setup(self, tries=0) -> bool:
        """Set up a phue bridge based on host parameter."""
        host = self.host
        hass = self.hass
        app_key: str = self.config_entry.data[CONF_API_KEY]
        websession = aiohttp_client.async_get_clientsession(hass)

        if self.use_v2:
            bridge = HueBridgeV2(host, app_key, websession)
        else:
            bridge = HueBridgeV1(host, app_key, websession)

        try:
            with async_timeout.timeout(10):
                await bridge.initialize()

        except (LinkButtonNotPressed, Unauthorized):
            # Usernames can become invalid if hub is reset or user removed.
            # We are going to fail the config entry setup and initiate a new
            # linking procedure. When linking succeeds, it will remove the
            # old config entry.
            create_config_flow(hass, host)
            return False
        except (
            asyncio.TimeoutError,
            client_exceptions.ClientOSError,
            client_exceptions.ServerDisconnectedError,
            client_exceptions.ContentTypeError,
        ) as err:
            raise ConfigEntryNotReady(
                f"Error connecting to the Hue bridge at {host}"
            ) from err

        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unknown error connecting to Hue bridge")
            return False

        # store actual aiohue bridge as api attribute
        self.api = bridge
        # store (this) bridge object in hass data
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

        # v2 specific initialization/setup code here
        if self.use_v2:
            self.parallel_updates_semaphore = asyncio.Semaphore(10)
            await async_setup_devices(hass, self.config_entry, self)
            hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS_v2)
        # v1 specific initialization/setup code here
        else:
            hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS_v1)
            if bridge.sensors is not None:
                self.sensor_manager = SensorManager(self)

        # add listener for config entry updates.
        self.reset_jobs.append(self.config_entry.add_update_listener(_update_listener))
        self.authorized = True
        return True

    async def async_request_call(self, task: Callable) -> Any:
        """Limit parallel requests to Hue hub.

        The Hue hub can only handle a certain amount of parallel requests, total.
        Although we limit our parallel requests, we still will run into issues because
        other products are hitting up Hue.

        ClientOSError means hub closed the socket on us.
        ContentResponseError means hub raised an error.
        Since we don't make bad requests, this is on them.
        """
        async with self.parallel_updates_semaphore:
            for tries in range(4):
                try:
                    return await task()
                except (
                    client_exceptions.ClientOSError,
                    client_exceptions.ClientResponseError,
                    client_exceptions.ServerDisconnectedError,
                ) as err:
                    if tries == 3:
                        self.logger.error("Request failed %s times, giving up", tries)
                        raise

                    # We only retry if it's a server error. So raise on all 4XX errors.
                    if (
                        isinstance(err, client_exceptions.ClientResponseError)
                        and err.status < HTTPStatus.INTERNAL_SERVER_ERROR
                    ):
                        raise

                    await asyncio.sleep(HUB_BUSY_SLEEP * tries)

    async def async_reset(self) -> bool:
        """Reset this bridge to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # The bridge can be in 3 states:
        #  - Setup was successful, self.api is not None
        #  - Authentication was wrong, self.api is None, not retrying setup.

        # If the authentication was wrong.
        if self.api is None:
            return True

        while self.reset_jobs:
            self.reset_jobs.pop()()

        # If setup was successful, we set api variable, forwarded entry and
        # register service
        unload_success = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS_v2 if self.use_v2 else PLATFORMS_v1
        )

        if unload_success:
            self.hass.data[DOMAIN].pop(self.config_entry.entry_id)

        return unload_success

    async def handle_unauthorized_error(self) -> None:
        """Create a new config flow when the authorization is no longer valid."""
        if not self.authorized:
            # we already created a new config flow, no need to do it again
            return
        self.logger.error(
            "Unable to authorize to bridge %s, setup the linking again", self.host
        )
        self.authorized = False
        create_config_flow(self.hass, self.host)


async def _update_listener(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Handle ConfigEntry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def create_config_flow(hass: core.HomeAssistant, host: str) -> None:
    """Start a config flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"host": host},
        )
    )
