"""Zimi Controller coordinator class device."""

import logging
import pprint

from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_TIMEOUT, CONF_VERBOSITY, CONF_WATCHDOG, PLATFORMS, ZIMI_WATCHDOG

_LOGGER = logging.getLogger(__name__)


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

        _LOGGER.debug(
            "Connecting to %s:%d with verbosity=%s, timeout=%d and watchdog=%d",
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_PORT],
            self.config_entry.data[CONF_VERBOSITY],
            self.config_entry.data[CONF_TIMEOUT],
            self.config_entry.data[CONF_WATCHDOG],
        )

        try:
            self.api = ControlPoint(
                description=ControlPointDescription(
                    host=self.config_entry.data[CONF_HOST],
                    port=self.config_entry.data[CONF_PORT],
                ),
                verbosity=self.config_entry.data[CONF_VERBOSITY],
                timeout=self.config_entry.data[CONF_TIMEOUT],
            )
            await self.api.connect()

        except ControlPointError as error:
            _LOGGER.error("Initiation failed: %s", error)
            raise ConfigEntryNotReady(error) from error

        if self.config_entry.data[CONF_MAC] != format_mac(self.api.mac):
            msg = f"Configured mac {self.config_entry.data[CONF_MAC]} != {format_mac(self.api.mac)}"
            _LOGGER.debug(msg=msg)

        if self.api.ready:
            _LOGGER.debug("Connected")
            _LOGGER.debug("\n%s", self.api.describe())

            if ZIMI_WATCHDOG > 0:
                self.api.start_watchdog(ZIMI_WATCHDOG)
                _LOGGER.debug("Started %d second watchdog", ZIMI_WATCHDOG)

            self.config_entry.runtime_data = self.api
            await self.hass.config_entries.async_forward_entry_setups(
                self.config_entry, PLATFORMS
            )
        else:
            msg = "Initiation failed: ZCC API not ready"
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
