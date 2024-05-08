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

from .const import CONTROLLER, DOMAIN, PLATFORMS, TIMEOUT, VERBOSITY, WATCHDOG

_LOGGER = logging.getLogger(__name__)


class ZimiController:
    """Manages a single Zimi Controller hub."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize."""
        self.controller: ControlPoint = None
        self.hass = hass
        self.config_entry = config

        _LOGGER.debug("Initialising:\n%s", pprint.pformat(self.config.data))

        # store (this) bridge object in hass data
        hass.data.setdefault(DOMAIN, {})[self.config.entry_id] = self

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return self.config.data[CONF_HOST]

    @property
    def port(self) -> int:
        """Return the host of this hub."""
        return self.config.data[CONF_PORT]

    @property
    def timeout(self) -> int:
        """Return the timeout of this hub."""
        return self.config.data[TIMEOUT]

    async def connect(self) -> bool:
        """Initialize Connection with the Zimi Controller."""
        try:
            _LOGGER.debug(
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
            _LOGGER.debug("Connected")
            _LOGGER.debug("\n%s", self.controller.describe())

            if self.watchdog > 0:
                self.controller.start_watchdog(self.watchdog)
                _LOGGER.debug("Started %d minute watchdog", self.watchdog)
        except ControlPointError as error:
            _LOGGER.error("Initiation failed: %s", error)
            raise ConfigEntryNotReady(error) from error

        if self.controller:
            self.hass.data[CONTROLLER] = self
            await self.hass.config_entries.async_forward_entry_setups(
                self.config, PLATFORMS
            )

        return True
    
    async def disconnect(self) -> bool:
        """Disconnect Zimi Controller."""

        if self.controller:
            self.controller.disconnect()
        else:
            return False

        return True    

    @property
    def verbosity(self) -> int:
        """Return the verbosity of this hub."""
        return self.config.data[VERBOSITY]

    @property
    def watchdog(self) -> int:
        """Return the watchdog timer of this hub."""
        return self.config.data[WATCHDOG]

    @property
    def zcc_verbosity(self) -> int:
        """Return the verbosity of the zcc-helper."""
        return self.config.data[VERBOSITY] - 1  # Reduced verbosity for zcc-helper
