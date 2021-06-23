"""The Mikrotik router class."""
from __future__ import annotations

from datetime import timedelta
import logging
import socket
import ssl
from types import MappingProxyType
from typing import Any

import librouteros
from librouteros.api import Api
from librouteros.login import plain as login_plain, token as login_token

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ARP,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    CAPSMAN,
    CLIENTS,
    CMD_PING,
    CONF_DETECTION_TIME,
    CONF_DHCP_SERVER_TRACK_MODE,
    CONF_USE_DHCP_SERVER,
    DEFAULT_DETECTION_TIME,
    DEFAULT_DHCP_SERVER_TRACK_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_DHCP_SERVER,
    DHCP,
    DOMAIN,
    IDENTITY,
    INFO,
    IS_CAPSMAN,
    IS_WIRELESS,
    MIKROTIK_SERVICES,
    NAME,
    WIRELESS,
)
from .errors import CannotConnect, LoginError
from .mikrotik_client import MikrotikClient

_LOGGER = logging.getLogger(__name__)


class MikrotikHubData:
    """Handle all communication with the Mikrotik API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: Api,
        registered_clients: dict[str, str | None],
    ) -> None:
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.api = api
        self.registered_clients = registered_clients
        self.host: str = self.config_entry.data[CONF_HOST]
        self.support_capsman: bool = False
        self.support_wireless: bool = False
        self.hostname: str | None = None
        self.model: str | None = None
        self.firmware: str | None = None
        self.serial_number: str | None = None

    @property
    def use_dhcp_server(self) -> bool:
        """Return DHCP server tracking option."""
        if self.support_capsman or self.support_wireless:
            return self.config_entry.options.get(
                CONF_USE_DHCP_SERVER, DEFAULT_USE_DHCP_SERVER
            )
        return True

    @property
    def dhcp_server_track_mode(self) -> str:
        """Return tracking mode when using DHCP server."""
        return self.config_entry.options.get(
            CONF_DHCP_SERVER_TRACK_MODE, DEFAULT_DHCP_SERVER_TRACK_MODE
        )

    @staticmethod
    def load_mac(clients: list[dict]) -> dict:
        """Load dictionary using MAC address as key."""
        mac_devices = {}
        for client in clients:
            if "mac-address" in client:
                mac = client["mac-address"]
                mac_devices[mac] = client
        return mac_devices

    def get_info(self, param: str) -> str | None:
        """Return device model name."""
        cmd = IDENTITY if param == NAME else INFO
        data = self.command(MIKROTIK_SERVICES[cmd])
        return (
            data[0].get(param)  # pylint: disable=unsubscriptable-object
            if data
            else None
        )

    def get_list_from_interface(self, interface: str) -> dict:
        """Get devices from interface."""
        result = self.command(MIKROTIK_SERVICES[interface])
        return self.load_mac(result) if result is not None else {}

    def get_hub_details(self) -> None:
        """Get Hub info."""
        self.hostname = self.get_info(NAME)
        self.model = self.get_info(ATTR_MODEL)
        self.firmware = self.get_info(ATTR_FIRMWARE)
        self.serial_number = self.get_info(ATTR_SERIAL_NUMBER)
        self.support_capsman = bool(self.command(MIKROTIK_SERVICES[IS_CAPSMAN]))
        self.support_wireless = bool(self.command(MIKROTIK_SERVICES[IS_WIRELESS]))

    def do_arp_ping(self, ip_address: str, interface: str) -> bool:
        """Attempt to arp ping MAC address via interface."""
        _LOGGER.debug("pinging - %s", ip_address)
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": ip_address,
        }

        data = self.command(CMD_PING, params)
        if data is not None:
            status = 0
            for result in data:  # pylint: disable=not-an-iterable
                if "status" in result:
                    status += 1
            if status == len(data):
                _LOGGER.debug(
                    "Mikrotik %s - %s arp_ping timed out", ip_address, interface
                )
                return False
        return True

    def command(self, cmd: str, params: dict | None = None) -> list[dict] | None:
        """Retrieve data from Mikrotik API."""
        params = params or {}
        _LOGGER.debug("Running command %s", cmd)
        try:
            response = list(self.api(cmd=cmd, **params))
        except (
            librouteros.exceptions.ConnectionClosed,
            OSError,
            socket.timeout,
        ) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self.host, api_error)
            raise CannotConnect from api_error
        except librouteros.exceptions.ProtocolError as api_error:
            _LOGGER.debug(
                "Mikrotik %s failed to retrieve data. cmd=[%s] Error: %s",
                self.host,
                cmd,
                api_error,
            )
            return None
        return response if response else None

    def update_devices(self) -> list[str]:
        """Update clients detected by the hub."""

        hub_clients = {}
        tracked_clients = []
        wireless_clients = arp_clients = dhcp_clients = {}
        all_clients: dict[str, MikrotikClient] = self.hass.data[DOMAIN][CLIENTS]

        dhcp_clients = self.get_list_from_interface(DHCP)

        if self.dhcp_server_track_mode == "ARP ping":
            _LOGGER.debug("Getting ARP device list")
            arp_clients = self.get_list_from_interface(ARP)

        if self.support_capsman:
            _LOGGER.debug("Hub is a CAPSMAN Manager")
            hub_clients = wireless_clients = self.get_list_from_interface(CAPSMAN)
        elif self.support_wireless:
            _LOGGER.debug("Hub supports WIRELESS Interface")
            hub_clients = wireless_clients = self.get_list_from_interface(WIRELESS)

        if self.use_dhcp_server:
            _LOGGER.debug("Tracking clients using DHCP server")
            hub_clients = dhcp_clients

        for mac in hub_clients:
            # don't add clients that are registered or detected by other configured hubs
            if mac not in list(set(all_clients) | set(self.registered_clients)) or (
                mac in self.registered_clients
                and self.registered_clients[mac] == self.config_entry.entry_id
            ):
                tracked_clients.append(mac)
                all_clients[mac] = MikrotikClient(
                    mac, dhcp_params=dhcp_clients.get(mac), host=self.host
                )

            if mac not in all_clients:
                continue

            # update wireless clients
            if mac in wireless_clients:
                all_clients[mac].update(
                    dhcp_params=dhcp_clients.get(mac),
                    wireless_params=wireless_clients[mac],
                    active=True,
                    host=self.host,
                )
                continue

            # update remaining clients
            if mac in dhcp_clients:
                if not dhcp_clients[mac].get("active-address"):
                    # don't update clients in dhcp_server with no active-address
                    continue
                active = True
                # ping check the rest of active devices if arp ping is enabled
                if self.dhcp_server_track_mode == "ARP ping" and mac in arp_clients:
                    if mac == "98:09:CF:0C:98:0F":
                        print("arp")
                    active = self.do_arp_ping(
                        arp_clients[mac]["address"],
                        arp_clients[mac]["interface"],
                    )
                if active:
                    all_clients[mac].update(
                        dhcp_params=dhcp_clients[mac],
                        active=True,
                        host=self.host,
                    )
        return tracked_clients


class MikrotikHub(DataUpdateCoordinator):
    """Mikrotik Hub Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self._mk_data: MikrotikHubData | None = None
        super().__init__(
            self.hass,
            _LOGGER,
            name=f"{DOMAIN} - {self.host}",
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return self.config_entry.data[CONF_HOST]

    @property
    def option_detection_time(self) -> timedelta:
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def hub_data(self):
        """Represent Mikrotik data object."""
        return self._mk_data

    async def async_update(self):
        """Update Mikrotik devices information."""
        try:
            return await self.hass.async_add_executor_job(self._mk_data.update_devices)
        except LoginError as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise UpdateFailed from err

    async def async_setup(self) -> None:
        """Set up the Mikrotik hub."""
        try:
            api = await self.hass.async_add_executor_job(
                get_api, self.config_entry.data
            )
        except CannotConnect as err:
            raise ConfigEntryNotReady from err
        except LoginError as err:
            raise ConfigEntryAuthFailed from err

        entity_registry: EntityRegistry = self.hass.helpers.entity_registry.async_get(
            self.hass
        )
        registered_clients = {
            entity.unique_id: entity.config_entry_id
            for entity in entity_registry.entities.values()
            if entity.platform == DOMAIN
        }
        self._mk_data = MikrotikHubData(
            self.hass, self.config_entry, api, registered_clients
        )
        await self.hass.async_add_executor_job(self._mk_data.get_hub_details)


def get_api(entry: MappingProxyType[str, Any]) -> Api:
    """Connect to Mikrotik hub."""
    _LOGGER.debug("Connecting to Mikrotik hub [%s]", entry[CONF_HOST])

    _login_method = (login_plain, login_token)
    kwargs = {"login_methods": _login_method, "port": entry["port"], "encoding": "utf8"}

    if entry[CONF_VERIFY_SSL]:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _ssl_wrapper = ssl_context.wrap_socket
        kwargs["ssl_wrapper"] = _ssl_wrapper

    try:
        api = librouteros.connect(
            entry[CONF_HOST],
            entry[CONF_USERNAME],
            entry[CONF_PASSWORD],
            **kwargs,
        )
        _LOGGER.debug("Connected to %s successfully", entry[CONF_HOST])
        return api
    except (
        librouteros.exceptions.LibRouterosError,
        OSError,
        socket.timeout,
    ) as api_error:
        _LOGGER.error("Mikrotik %s error: %s", entry[CONF_HOST], api_error)
        if "invalid user name or password" in str(api_error):
            raise LoginError from api_error
        raise CannotConnect from api_error
