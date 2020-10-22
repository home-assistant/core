"""Hub for communication with 1-Wire server or mount_dir."""
import logging
import os

from pyownet import protocol

from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


class OneWireHub:
    """Hub to communicate with SysBus or OWServer."""

    def __init__(self, hass: HomeAssistantType):
        """Initialize."""
        self.hass = hass

    async def can_connect(self, host, port) -> bool:
        """Test if we can authenticate with the host."""
        try:
            await self.hass.async_add_executor_job(protocol.proxy, host, port)
        except (protocol.Error, protocol.ConnError) as exc:
            _LOGGER.error(
                "Cannot connect to owserver on %s:%d, got: %s", host, port, exc
            )
            return False
        return True

    async def is_valid_mount_dir(self, mount_dir) -> bool:
        """Test that the mount_dir is a valid path."""
        if not await self.hass.async_add_executor_job(os.path.isdir, mount_dir):
            _LOGGER.error("Cannot find directory %s", mount_dir)
            return False
        return True
