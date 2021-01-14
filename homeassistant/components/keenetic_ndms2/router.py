"""The Keenetic Client class."""
from datetime import timedelta
import logging
from typing import Callable, Dict, Optional

from ndms2_client import Client, ConnectionException, Device, TelnetConnection
from ndms2_client.client import RouterInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KeeneticRouter:
    """Keenetic client Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.last_devices = {}  # type: Dict[str, Device]
        self._router_info = None  # type: Optional[RouterInfo]
        self._client = None  # type: Optional[Client]
        self._cancel_periodic_update = None  # type: Optional[Callable]
        self._available = False
        self.progress = None

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data[CONF_HOST]

    @property
    def device_info(self):
        """Return the host of this hub."""
        return {
            "identifiers": {(DOMAIN, f"router-{self.config_entry.entry_id}")},
            "manufacturer": self.manufacturer,
            "model": self.model,
            "name": self.name,
            "sw_version": self.firmware,
        }

    @property
    def name(self):
        """Return the name of the hub."""
        return self._router_info.name if self._router_info else self.host

    @property
    def model(self):
        """Return the model of the hub."""
        return self._router_info.model if self._router_info else None

    @property
    def firmware(self):
        """Return the firmware of the hub."""
        return self._router_info.fw_version if self._router_info else None

    @property
    def manufacturer(self):
        """Return the firmware of the hub."""
        return self._router_info.manufacturer if self._router_info else None

    @property
    def available(self):
        """Return if the hub is connected."""
        return self._available

    @property
    def consider_home_interval(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(seconds=self.config_entry.options[CONF_CONSIDER_HOME])

    @property
    def signal_update(self):
        """Event specific per router entry to signal updates."""
        return f"keenetic-update-{self.config_entry.entry_id}"

    async def async_add_defaults(self):
        """Populate default options."""
        data = dict(self.config_entry.data)
        options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME,
            CONF_INTERFACES: [DEFAULT_INTERFACE],
            CONF_TRY_HOTSPOT: True,
            CONF_INCLUDE_ARP: True,
            CONF_INCLUDE_ASSOCIATED: True,
            **self.config_entry.options,
        }

        if options.keys() - self.config_entry.options.keys():
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options=options
            )

    async def request_update(self):
        """Request an update."""
        if self.progress is not None:
            await self.progress
            return

        self.progress = self.hass.async_create_task(self.async_update())
        await self.progress

        self.progress = None

    async def async_update(self):
        """Update devices information."""
        await self.hass.async_add_executor_job(self._update_devices)
        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up the connection."""
        self._client = Client(
            TelnetConnection(
                self.config_entry.data[CONF_HOST],
                self.config_entry.data[CONF_PORT],
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
        )

        try:
            await self.hass.async_add_executor_job(self._update_router_info)
        except ConnectionException as error:
            raise ConfigEntryNotReady from error

        await self.async_add_defaults()

        async def async_update_data(_now):
            await self.request_update()
            self._cancel_periodic_update = async_track_point_in_utc_time(
                self.hass,
                async_update_data,
                dt_util.utcnow()
                + timedelta(seconds=self.config_entry.options[CONF_SCAN_INTERVAL]),
            )

        await async_update_data(dt_util.utcnow())

    async def async_teardown(self):
        """Teardown up the connection."""
        if self._cancel_periodic_update:
            self._cancel_periodic_update()

    def _update_router_info(self):
        try:
            self._router_info = self._client.get_router_info()
            self._available = True
        except Exception:
            self._available = False
            raise

    def _update_devices(self):
        """Get ARP from keenetic router."""
        _LOGGER.debug("Fetching devices from router...")

        try:
            _response = self._client.get_devices(
                try_hotspot=self.config_entry.options[CONF_TRY_HOTSPOT],
                include_arp=self.config_entry.options[CONF_INCLUDE_ARP],
                include_associated=self.config_entry.options[CONF_INCLUDE_ASSOCIATED],
            )
            self.last_devices = {
                dev.mac: dev
                for dev in _response
                if dev.interface in self.config_entry.options[CONF_INTERFACES]
            }
            _LOGGER.debug("Successfully fetched data from router: %s", str(_response))
            self._router_info = self._client.get_router_info()
            self._available = True

        except ConnectionException:
            _LOGGER.error("Error fetching data from router")
            self._available = False
