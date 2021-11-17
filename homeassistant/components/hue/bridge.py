"""Code to handle a Hue bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import client_exceptions
from aiohue import HueBridgeV1, HueBridgeV2, LinkButtonNotPressed, Unauthorized
from aiohue.errors import AiohueException
import async_timeout

from homeassistant import core
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_API_VERSION, DOMAIN
from .v1.sensor_base import SensorManager
from .v2.device import async_setup_devices
from .v2.hue_event import async_setup_hue_events

# How long should we sleep if the hub is busy
HUB_BUSY_SLEEP = 0.5

PLATFORMS_v1 = ["light", "binary_sensor", "sensor"]
PLATFORMS_v2 = ["light", "binary_sensor", "sensor", "scene", "switch"]


class HueBridge:
    """Manages a single Hue bridge."""

    def __init__(self, hass: core.HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.authorized = False
        self.parallel_updates_semaphore = asyncio.Semaphore(
            3 if self.api_version == 1 else 10
        )
        # Jobs to be executed when API is reset.
        self.reset_jobs: list[core.CALLBACK_TYPE] = []
        self.sensor_manager: SensorManager | None = None
        self.logger = logging.getLogger(__name__)
        # store actual api connection to bridge as api
        app_key: str = self.config_entry.data[CONF_API_KEY]
        websession = aiohttp_client.async_get_clientsession(hass)
        if self.api_version == 1:
            self.api = HueBridgeV1(self.host, app_key, websession)
        else:
            self.api = HueBridgeV2(self.host, app_key, websession)
        # store (this) bridge object in hass data
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

    @property
    def host(self) -> str:
        """Return the host of this bridge."""
        return self.config_entry.data[CONF_HOST]

    @property
    def api_version(self) -> int:
        """Return api version we're set-up for."""
        return self.config_entry.data[CONF_API_VERSION]

    async def async_initialize_bridge(self) -> bool:
        """Initialize Connection with the Hue API."""
        try:
            with async_timeout.timeout(10):
                await self.api.initialize()

        except (LinkButtonNotPressed, Unauthorized):
            # Usernames can become invalid if hub is reset or user removed.
            # We are going to fail the config entry setup and initiate a new
            # linking procedure. When linking succeeds, it will remove the
            # old config entry.
            create_config_flow(self.hass, self.host)
            return False
        except (
            asyncio.TimeoutError,
            client_exceptions.ClientOSError,
            client_exceptions.ServerDisconnectedError,
            client_exceptions.ContentTypeError,
        ) as err:
            raise ConfigEntryNotReady(
                f"Error connecting to the Hue bridge at {self.host}"
            ) from err
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unknown error connecting to Hue bridge")
            return False

        # v1 specific initialization/setup code here
        if self.api_version == 1:
            if self.api.sensors is not None:
                self.sensor_manager = SensorManager(self)
            self.hass.config_entries.async_setup_platforms(
                self.config_entry, PLATFORMS_v1
            )

        # v2 specific initialization/setup code here
        else:
            await async_setup_devices(self)
            await async_setup_hue_events(self)
            self.hass.config_entries.async_setup_platforms(
                self.config_entry, PLATFORMS_v2
            )

        # add listener for config entry updates.
        self.reset_jobs.append(self.config_entry.add_update_listener(_update_listener))
        self.authorized = True
        return True

    async def async_request_call(
        self, task: Callable, *args, allowed_errors: list[str] | None = None, **kwargs
    ) -> Any:
        """Limit parallel requests to Hue hub.

        The Hue hub can only handle a certain amount of parallel requests, total.
        Although we limit our parallel requests, we still will run into issues because
        other products are hitting up Hue.

        ClientOSError means hub closed the socket on us.
        ContentResponseError means hub raised an error.
        Since we don't make bad requests, this is on them.
        """
        max_tries = 5
        async with self.parallel_updates_semaphore:
            for tries in range(max_tries):
                try:
                    return await task(*args, **kwargs)
                except AiohueException as err:
                    # The new V2 api is a bit more fanatic with throwing errors
                    # some of which we accept in certain conditions
                    # handle that here. Note that these errors are strings and do not have
                    # an identifier or something.
                    if allowed_errors is not None and str(err) in allowed_errors:
                        # log only
                        self.logger.debug(
                            "Ignored error/warning from Hue API: %s", str(err)
                        )
                        return None
                    raise err
                except (
                    client_exceptions.ClientOSError,
                    client_exceptions.ClientResponseError,
                    client_exceptions.ServerDisconnectedError,
                ) as err:
                    if tries == max_tries:
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

        # Unload platforms
        unload_success = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS_v1 if self.api_version == 1 else PLATFORMS_v2
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
