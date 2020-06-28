"""Support for Broadlink devices."""
from functools import partial
import logging

from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    ConnectionClosedError,
    DeviceOfflineError,
)

from .const import DEFAULT_RETRY

_LOGGER = logging.getLogger(__name__)


class BroadlinkDevice:
    """Manages a Broadlink device."""

    def __init__(self, hass, api):
        """Initialize the device."""
        self.hass = hass
        self.api = api
        self.available = None

    async def async_connect(self):
        """Connect to the device."""
        try:
            await self.hass.async_add_executor_job(self.api.auth)
        except BroadlinkException as err_msg:
            if self.available:
                self.available = False
                _LOGGER.warning(
                    "Disconnected from device at %s: %s", self.api.host[0], err_msg
                )
            return False
        else:
            if not self.available:
                if self.available is not None:
                    _LOGGER.warning("Connected to device at %s", self.api.host[0])
                self.available = True
            return True

    async def async_request(self, function, *args, **kwargs):
        """Send a request to the device."""
        partial_function = partial(function, *args, **kwargs)
        for attempt in range(DEFAULT_RETRY):
            try:
                result = await self.hass.async_add_executor_job(partial_function)
            except (AuthorizationError, ConnectionClosedError, DeviceOfflineError):
                if attempt == DEFAULT_RETRY - 1 or not await self.async_connect():
                    raise
            else:
                if not self.available:
                    self.available = True
                    _LOGGER.warning("Connected to device at %s", self.api.host[0])
                return result
