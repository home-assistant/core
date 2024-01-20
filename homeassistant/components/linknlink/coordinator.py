"""LinknLink Coordinator."""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
from functools import partial
import logging
from typing import Any

import linknlink as llk
from linknlink.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConnectionClosedError,
    LinknLinkException,
    NetworkTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LinknLinkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """In charge of get the data for a site."""

    api: llk.Device
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, mac: str) -> None:
        """Initialize the data service."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{mac}",
            update_interval=timedelta(seconds=30),
        )
        self.fw_version: int | None = None
        self.authorized: bool | None = None

    @property
    def available(self) -> bool | None:
        """Return True if the device is available."""
        return self.authorized

    def _get_firmware_version(self) -> int | None:
        """Get firmware version."""
        self.api.auth()
        with suppress(LinknLinkException, OSError):
            return self.api.get_fwversion()
        return None

    async def async_setup(self) -> bool:
        """Set up the device and related entities."""
        config = self.config_entry

        api = llk.gendevice(
            config.data[CONF_TYPE],
            (config.data[CONF_HOST], DEFAULT_PORT),
            bytes.fromhex(config.data[CONF_MAC]),
            name=config.title,
        )
        self.api = api
        try:
            self.fw_version = await self.hass.async_add_executor_job(
                self._get_firmware_version
            )

        except AuthenticationError:
            await self._async_handle_auth_error()
            return False

        except (NetworkTimeoutError, OSError) as err:
            _LOGGER.error("Failed to connect to the device [%s]: %s", api.host[0], err)
            return False

        except LinknLinkException as err:
            _LOGGER.error(
                "Failed to authenticate to the device at %s: %s", api.host[0], err
            )
            return False

        self.authorized = True

        return True

    async def _async_handle_auth_error(self) -> None:
        """Handle an authentication error."""
        if self.authorized is False:
            return

        self.authorized = False

        _LOGGER.error(
            (
                "%s (%s at %s) is locked. Click Configuration in the sidebar, "
                "click Integrations, click Configure on the device and follow "
                "the instructions to unlock it"
            ),
            self.name,
            self.api.model,
            self.api.host[0],
        )

    async def async_auth(self) -> bool:
        """Authenticate to the device."""
        try:
            await self.hass.async_add_executor_job(self.api.auth)
        except (LinknLinkException, OSError) as err:
            _LOGGER.debug(
                "Failed to authenticate to the device at %s: %s", self.api.host[0], err
            )
            if isinstance(err, AuthenticationError):
                await self._async_handle_auth_error()
            return False
        return True

    async def async_request(self, function, *args, **kwargs):
        """Send a request to the device."""
        request = partial(function, *args, **kwargs)
        try:
            return await self.hass.async_add_executor_job(request)
        except (AuthorizationError, ConnectionClosedError):
            if not await self.async_auth():
                raise
            return await self.hass.async_add_executor_job(request)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            data = await self.async_request(self.api.check_sensors)
            return data
        except AttributeError as e:
            _LOGGER.error("Failed to execute function: %s", e)
            return {}
