"""Implement JVC component."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging

from jvc_projector import JVCProjector
import voluptuous as vol

from homeassistant.components.remote import PLATFORM_SCHEMA, RemoteEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    GAMING_MODE_HDR_COMMAND,
    GAMING_MODE_SDR_COMMAND,
    HDR_MODE_COMMAND,
    INFO_COMMAND,
    SDR_MODE_COMMAND,
)

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up platform."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)

    async_add_entities(
        [
            JVCRemote(name, host, password),
        ]
    )

    platform = entity_platform.async_get_current_platform()
    # Register the services
    platform.async_register_entity_service(
        INFO_COMMAND, {}, f"service_async_{INFO_COMMAND}"
    )
    platform.async_register_entity_service(
        GAMING_MODE_HDR_COMMAND, {}, f"service_async_{GAMING_MODE_HDR_COMMAND}"
    )
    platform.async_register_entity_service(
        GAMING_MODE_SDR_COMMAND, {}, f"service_async_{GAMING_MODE_SDR_COMMAND}"
    )
    platform.async_register_entity_service(
        HDR_MODE_COMMAND, {}, f"service_async_{HDR_MODE_COMMAND}"
    )
    platform.async_register_entity_service(
        SDR_MODE_COMMAND, {}, f"service_async_{SDR_MODE_COMMAND}"
    )


class JVCRemote(RemoteEntity):
    """Implements the interface for JVC Remote in HA."""

    def __init__(self, name, host, password, timeout: str = None) -> None:
        """JVC Init."""
        self._name = name
        self._host = host
        # Timeout for connections. Everything takes less than 3 seconds to run
        if timeout is None:
            self.timeout = 5
        else:
            self.timeout = int(timeout)
        # use 5 second timeout, try to prevent error loops
        self.jvc_client = JVCProjector(
            host=host, password=password, logger=_LOGGER, connect_timeout=self.timeout
        )
        self._state = False
        self._ll_state = False
        # Because we can only have one connection at a time, we need to lock every command
        # otherwise JVC's server implementation will cancel the running command
        # and just confuse everything, then cause HA to freak out
        self._lock = asyncio.Lock()

    @property
    def should_poll(self):
        """Poll."""
        # Polling is disabled as it is unreliable and will lock up commands at the moment
        # Requires adding stronger locking and command buffering
        return False

    @property
    def name(self):
        """Name."""
        return self._name

    @property
    def host(self):
        """Host."""
        return self._host

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        # These are bools. Useful for making sensors
        return {
            "power_state": self._state,
            "low_latency": self._ll_state,
            "host_ip": self._host,
            "timeout": self.timeout,
            # "command_in_flight": self._lock.locked(),
        }

    @property
    def is_on(self):
        """Return the last known state of the projector."""

        return self._state

    async def async_turn_on(self, **kwargs):
        """Send the power on command."""

        async with self._lock:
            await self.jvc_client.async_power_on()
            self._state = True

    async def async_turn_off(self, **kwargs):
        """Send the power off command."""

        async with self._lock:
            await self.jvc_client.async_power_off()
            self._state = False

    async def async_update(self):
        """Retrieve latest state."""
        # Not implemented yet
        # self._state = await self.jvc_client.async_is_on()
        # self._ll_state = await self.jvc_client.async_get_low_latency_state()

    async def async_send_command(self, command: Iterable[str], **kwargs):
        """Send commands to a device."""

        async with self._lock:
            await self.jvc_client.async_exec_command(command)

    async def service_async_info(self) -> None:
        """Bring up the info screen."""

        async with self._lock:
            await self.jvc_client.async_info()

    async def service_async_gaming_mode_hdr(self) -> None:
        """Set optimal gaming modes."""

        async with self._lock:
            await self.jvc_client.async_gaming_mode_hdr()
            self._ll_state = True

    async def service_async_gaming_mode_sdr(self) -> None:
        """Set optimal gaming modes."""

        async with self._lock:
            await self.jvc_client.async_gaming_mode_sdr()
            self._ll_state = True

    async def service_async_hdr_picture_mode(self) -> None:
        """Set optimal HDR modes."""

        async with self._lock:
            await self.jvc_client.async_hdr_picture_mode()
            self._ll_state = False

    async def service_async_sdr_picture_mode(self) -> None:
        """Set optimal SDR modes."""

        async with self._lock:
            await self.jvc_client.async_sdr_picture_mode()
            self._ll_state = False
