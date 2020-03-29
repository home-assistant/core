"""Code to handle a Pulse Hub."""
import asyncio
from typing import Optional

import aiopulse

from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER
from .errors import CannotConnect


class PulseHub:
    """Manages a single Pulse Hub."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.available = True
        self.authorized = False
        self.api: Optional[aiopulse.Hub] = None
        self.parallel_updates_semaphore = None
        self.task = None

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data["host"]

    async def async_setup(self, tries=0):
        """Set up a Pulse Hub based on host parameter."""
        host = self.host
        hass = self.hass

        hub = aiopulse.Hub(host)

        try:
            # Create a Hub object and verify connection.
            try:
                # self.task = hass.async_create_task(hub.run())
                self.task = asyncio.create_task(hub.run())
                LOGGER.debug("Hub running")
            except (aiopulse.InvalidResponseException):
                raise CannotConnect

            except (asyncio.TimeoutError):
                raise CannotConnect

        except CannotConnect:
            LOGGER.error("Error connecting to the Pulse Hub at %s", host)
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unknown error connecting with Pulse Hub at %s", host)
            return False

        self.api = hub

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(self.config_entry, "cover")
        )

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(self.config_entry, "sensor")
        )

        self.parallel_updates_semaphore = asyncio.Semaphore(10)

        self.authorized = True
        LOGGER.debug("Hub setup complete")
        return True

    async def async_request_call(self, coro):
        """Process request batched."""

        async with self.parallel_updates_semaphore:
            return await coro

    async def async_reset(self):
        """Reset this hub to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # The hub can be in 3 states:
        #  - Setup was successful, self.api is not None
        #  - Authentication was wrong, self.api is None, not retrying setup.

        # If the authentication was wrong.
        if self.api is None:
            return True

        await self.api.stop()

        # If setup was successful, we set api variable, forwarded entry and
        # register service
        results = await asyncio.gather(
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "cover"
            ),
        )
        # None and True are OK
        return False not in results

    async def async_update(self):
        """Update the device with the latest data."""
        LOGGER.error("updating hub")
        await self.api.update()
        LOGGER.error("update complete")
