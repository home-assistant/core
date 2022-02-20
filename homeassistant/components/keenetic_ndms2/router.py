"""The Keenetic Client class."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging

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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KeeneticRouter:
    """Keenetic client Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Client."""
        self.hass = hass
        self.config_entry = config_entry
        self._last_devices: dict[str, Device] = {}
        self._router_info: RouterInfo | None = None
        self._connection: TelnetConnection | None = None
        self._client: Client | None = None
        self._cancel_periodic_update: Callable | None = None
        self._available = False
        self._progress = None
        self._tracked_interfaces = set(config_entry.options[CONF_INTERFACES])

    @property
    def client(self):
        """Read-only accessor for the client connection."""
        return self._client

    @property
    def last_devices(self):
        """Read-only accessor for last_devices."""
        return self._last_devices

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data[CONF_HOST]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the host of this hub."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"router-{self.config_entry.entry_id}")},
            manufacturer=self.manufacturer,
            model=self.model,
            name=self.name,
            sw_version=self.firmware,
        )

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
    def tracked_interfaces(self):
        """Tracked interfaces."""
        return self._tracked_interfaces

    @property
    def signal_update(self):
        """Event specific per router entry to signal updates."""
        return f"keenetic-update-{self.config_entry.entry_id}"

    async def request_update(self):
        """Request an update."""
        if self._progress is not None:
            await self._progress
            return

        self._progress = self.hass.async_create_task(self.async_update())
        await self._progress

        self._progress = None

    async def async_update(self):
        """Update devices information."""
        await self.hass.async_add_executor_job(self._update_devices)
        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up the connection."""
        self._connection = TelnetConnection(
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_PORT],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_PASSWORD],
        )
        self._client = Client(self._connection)

        try:
            await self.hass.async_add_executor_job(self._update_router_info)
        except ConnectionException as error:
            raise ConfigEntryNotReady from error

        async def async_update_data(_now):
            await self.request_update()
            self._cancel_periodic_update = async_call_later(
                self.hass,
                self.config_entry.options[CONF_SCAN_INTERVAL],
                async_update_data,
            )

        await async_update_data(dt_util.utcnow())

    async def async_teardown(self):
        """Teardown up the connection."""
        if self._cancel_periodic_update:
            self._cancel_periodic_update()
        self._connection.disconnect()

    def _update_router_info(self):
        try:
            self._router_info = self._client.get_router_info()
            self._available = True
        except Exception:
            self._available = False
            raise

    def _update_devices(self):
        """Get ARP from keenetic router."""
        _LOGGER.debug("Fetching devices from router")

        try:
            _response = self._client.get_devices(
                try_hotspot=self.config_entry.options[CONF_TRY_HOTSPOT],
                include_arp=self.config_entry.options[CONF_INCLUDE_ARP],
                include_associated=self.config_entry.options[CONF_INCLUDE_ASSOCIATED],
            )
            self._last_devices = {
                dev.mac: dev
                for dev in _response
                if dev.interface in self._tracked_interfaces
            }
            _LOGGER.debug("Successfully fetched data from router: %s", str(_response))
            self._router_info = self._client.get_router_info()
            self._available = True

        except ConnectionException:
            _LOGGER.error("Error fetching data from router")
            self._available = False
