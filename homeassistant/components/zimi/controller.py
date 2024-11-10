"""Zimi Controller wrapper class device."""

import logging
import pprint

from zcc import (
    ControlPoint,
    ControlPointDescription,
    ControlPointDiscoveryService,
    ControlPointError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_TIMEOUT, CONF_VERBOSITY, CONF_WATCHDOG, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class ZimiController:
    """Manages a single Zimi Controller hub."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize."""
        self.controller: ControlPoint = None
        self.hass = hass
        self.config_entry = config

        if self.config_entry.data.get(CONF_VERBOSITY, 0) > 1:
            _LOGGER.setLevel(logging.DEBUG)

        _LOGGER.debug("Initialising:\n%s", pprint.pformat(self.config_entry.data))

        # store (this) bridge object in hass data
        hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return self.config_entry.data[CONF_HOST]

    @property
    def port(self) -> int:
        """Return the host of this hub."""
        return self.config_entry.data[CONF_PORT]

    @property
    def timeout(self) -> int:
        """Return the timeout of this hub."""
        return self.config_entry.data[CONF_TIMEOUT]

    async def connect(self) -> bool:
        """Initialize Connection with the Zimi Controller."""
        try:
            _LOGGER.info(
                "Connecting to %s:%d with verbosity=%s, timeout=%d and watchdog=%d",
                self.host,
                self.port,
                self.zcc_verbosity,
                self.timeout,
                self.watchdog,
            )
            if self.host == "":
                description = await ControlPointDiscoveryService().discover()
            else:
                description = ControlPointDescription(host=self.host, port=self.port)

            self.controller = ControlPoint(
                description=description,
                verbosity=self.zcc_verbosity,
                timeout=self.timeout,
            )
            await self.controller.connect()
            _LOGGER.info("Connected")
            _LOGGER.info("\n%s", self.controller.describe())

            if self.watchdog > 0:
                self.controller.start_watchdog(self.watchdog)
                _LOGGER.debug("Started %d minute watchdog", self.watchdog)
        except ControlPointError as error:
            _LOGGER.error("Initiation failed: %s", error)
            raise ConfigEntryNotReady(error) from error

        if self.controller:
            # self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)
            self.config_entry.runtime_data = self
            await self.hass.config_entries.async_forward_entry_setups(
                self.config_entry, PLATFORMS
            )

        return True

    async def disconnect(self) -> bool:
        """Disconnect connection with the Zimi controller."""
        return self.controller.disconnect()

    @property
    def verbosity(self) -> int:
        """Return the verbosity of this hub."""
        return self.config_entry.data[CONF_VERBOSITY]

    @property
    def watchdog(self) -> int:
        """Return the watchdog timer of this hub."""
        return self.config_entry.data[CONF_WATCHDOG]

    @property
    def zcc_verbosity(self) -> int:
        """Return the verbosity of the zcc-helper."""
        return (
            self.config_entry.data[CONF_VERBOSITY] - 1
        )  # Reduced verbosity for zcc-helper
