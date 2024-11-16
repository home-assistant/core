"""Zimi Controller coordinator class device."""

import logging
import pprint

from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_connect_to_controller(
    host: str, port: int, fast: bool = False
) -> ControlPoint | None:
    """Connect to Zimi Cloud Controller with defined parameters."""

    _LOGGER.debug("Connecting to %s:%d", host, port)

    try:
        api = ControlPoint(
            description=ControlPointDescription(
                host=host,
                port=port,
            )
        )
        await api.connect(fast=fast)

    except ControlPointError as error:
        _LOGGER.error("Connection failed: %s", error)
        raise ConfigEntryNotReady(error) from error

    if api.ready:
        _LOGGER.debug("Connected")

        if not fast:
            api.start_watchdog()
            _LOGGER.debug("Started watchdog")

        return api

    msg = "Connection failed: not ready"
    _LOGGER.error(msg=msg)

    return None


class ZimiCoordinator(DataUpdateCoordinator):
    """Coordinates a single Zimi Controller hub.

    Initial list of devices is fetched in _async_setup() but all subsequent data
    is pushed from the zcc helper and handled in the Entities.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Zimi Cloud Connect",
            always_update=False,
        )

        if self.config_entry:
            _LOGGER.debug("Initialising:\n%s", pprint.pformat(self.config_entry.data))

        self.api: ControlPoint | None = None

    async def _async_setup(self):
        """Set up the coordinator."""

        try:
            self.api = await async_connect_to_coordinator(
                host=self.config_entry.data[CONF_HOST],
                port=self.config_entry.data[CONF_PORT],
            )

        except ControlPointError as error:
            _LOGGER.error("Initiation failed: %s", error)
            raise ConfigEntryNotReady(error) from error

        if self.api:
            _LOGGER.debug("\n%s", self.api.describe())

            self.config_entry.runtime_data = self.api
            await self.hass.config_entries.async_forward_entry_setups(
                self.config_entry, PLATFORMS
            )
        else:
            msg = "Initiation failed: not ready"
            _LOGGER.error(msg=msg)
            raise ConfigEntryNotReady(msg)

    async def _async_update_data(self):
        """Fetch data from API.

        This is not used in this integration - each Entity subscribes
        to a notification from the ControlPointDevice directly.
        """

    async def disconnect(self) -> None:
        """Disconnect the coordinator."""
        if self.api:
            self.api.disconnect()
            self.api = None
        if self.config_entry:
            self.config_entry.runtime_data = None
