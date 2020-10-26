"""Hub for communication with 1-Wire server or mount_dir."""
import os

from pyownet import protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_MOUNT_DIR, CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS


class OneWireHub:
    """Hub to communicate with SysBus or OWServer."""

    def __init__(self, hass: HomeAssistantType):
        """Initialize."""
        self.hass = hass
        self.owproxy: protocol._Proxy = None

    async def connect(self, host: str, port: int) -> None:
        """Connect to the owserver host."""
        try:
            self.owproxy = await self.hass.async_add_executor_job(
                protocol.proxy, host, port
            )
        except protocol.ConnError as exc:
            raise CannotConnect from exc

    async def check_mount_dir(self, mount_dir: str) -> None:
        """Test that the mount_dir is a valid path."""
        if not await self.hass.async_add_executor_job(os.path.isdir, mount_dir):
            raise InvalidPath

    async def initialize(self, config_entry: ConfigEntry) -> None:
        """Initialize a config entry."""
        if config_entry.data[CONF_TYPE] == CONF_TYPE_SYSBUS:
            await self.check_mount_dir(config_entry.data[CONF_MOUNT_DIR])
        elif config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER:
            host = config_entry.data[CONF_HOST]
            port = config_entry.data[CONF_PORT]
            try:
                await self.connect(host, port)
            except CannotConnect as exc:
                raise PlatformNotReady() from exc


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidPath(HomeAssistantError):
    """Error to indicate the path is invalid."""
