"""Mikrotik Hub class."""
import logging
import socket
import ssl

import librouteros
from librouteros.login import plain, token

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import (
    ARP,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    CAPSMAN,
    CONF_ARP_PING,
    CONF_FORCE_DHCP,
    CONF_HUBS,
    DHCP,
    IDENTITY,
    INFO,
    IS_CAPSMAN,
    IS_WIRELESS,
    MIKROTIK_SERVICES,
    NAME,
    WIRELESS,
)
from .errors import CannotConnect, LoginError, MikrotikError
from .mikrotik_client import MikrotikClient

_LOGGER = logging.getLogger(__name__)


class MikrotikHub:
    """Represent Mikrotik hub."""

    def __init__(self, hass, config_entry, hub, clients):
        """Initialize the Mikrotik hub."""
        self.hass = hass
        self.config_entry = config_entry
        self.data = config_entry.data[CONF_HUBS][hub]
        self.api = None
        self.clients = clients
        self.available = True
        self._support_capsman = False
        self._support_wireless = False
        self._support_wired = False
        self._hostname = None
        self._hub_info = {}

    @property
    def host(self):
        """Return the host of this hub."""
        return self.data[CONF_HOST]

    @property
    def name(self):
        """Return the hostname of the hub."""
        return self._hostname

    @property
    def model(self):
        """Return the model of the hub."""
        return self._hub_info.get(ATTR_MODEL)

    @property
    def firmware(self):
        """Return the firmware of the hub."""
        return self._hub_info.get(ATTR_FIRMWARE)

    @property
    def serial_number(self):
        """Return the serial number of the hub."""
        return self._hub_info.get(ATTR_SERIAL_NUMBER)

    @property
    def arp_enabled(self):
        """Return arp_ping option setting."""
        return self.config_entry.options.get(CONF_ARP_PING, False)

    @property
    def force_dhcp(self):
        """Return force_dhcp option setting."""
        return self.config_entry.options.get(CONF_FORCE_DHCP, False)

    @staticmethod
    def load_mac(devices=None):
        """Load dictionary using MAC address as key."""
        if not devices:
            return None
        mac_devices = {}
        for device in devices:
            if "mac-address" in device:
                mac = device["mac-address"]
                mac_devices[mac] = device
        return mac_devices

    def get_info(self, cmd):
        """Return param details."""
        data = self.command(MIKROTIK_SERVICES[cmd])
        return data[0] if data else None

    def get_list_from_interface(self, interface):
        """Return clients from interface."""
        result = self.command(MIKROTIK_SERVICES[interface])
        return self.load_mac(result) if result else {}

    def get_hub_details(self):
        """Get hub info."""
        self._hostname = self.get_info(IDENTITY).get(NAME)
        self._hub_info = self.get_info(INFO)
        self._support_capsman = bool(self.command(MIKROTIK_SERVICES[IS_CAPSMAN]))
        self._support_wireless = bool(self.command(MIKROTIK_SERVICES[IS_WIRELESS]))
        self._support_wired = not (self._support_wireless or self._support_capsman)

    def connect_to_hub(self):
        """Connect to hub."""
        try:
            self.api = get_api(self.hass, self.data)
            self.available = True
        except MikrotikError as err:
            self.available = False
            raise err

        self.get_hub_details()
        return True

    def do_arp_ping(self, ip_address, interface):
        """Attempt to arp ping MAC address via interface."""
        _LOGGER.debug("pinging - %s", ip_address)
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": ip_address,
        }
        cmd = "/ping"
        data = self.command(cmd, params)
        if data is not None:
            status = 0
            for result in data:
                if "status" in result:
                    status += 1
            if status == len(data):
                _LOGGER.debug(
                    "Mikrotik %s - %s arp_ping timed out", ip_address, interface
                )
                return False
        return True

    def command(self, cmd, params=None):
        """Retrieve data from Mikrotik API."""
        _LOGGER.debug("Running command %s", cmd)
        params = params or {}
        try:
            response = list(self.api(cmd=cmd, **params))
        except (
            librouteros.exceptions.ConnectionClosed,
            OSError,
            socket.timeout,
        ) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self.host, api_error)
            raise CannotConnect
        except librouteros.exceptions.ProtocolError as api_error:
            _LOGGER.warning(
                "Mikrotik %s failed to retrieve data. cmd=[%s] Error: %s",
                self.host,
                cmd,
                api_error,
            )
            return None
        return response

    def update_clients(self):
        """Update clients with latest status."""
        if not self.available or not self.api:
            try:
                self.connect_to_hub()
            except MikrotikError:
                return

        _LOGGER.debug("updating network clients for host: %s", self.host)
        client_list = wireless_clients = arp_clients = dhcp_clients = {}

        try:
            dhcp_clients = self.get_list_from_interface(DHCP)
            if self.arp_enabled:
                _LOGGER.debug("Getting ARP device list")
                arp_clients = self.get_list_from_interface(ARP)

            if self._support_capsman:
                _LOGGER.debug("Hub is a CAPSMAN Manager")
                client_list = wireless_clients = self.get_list_from_interface(CAPSMAN)
            elif self._support_wireless:
                _LOGGER.debug("Hub supports WIRELESS Interface")
                client_list = wireless_clients = self.get_list_from_interface(WIRELESS)

            if not client_list or self.force_dhcp:
                _LOGGER.debug("using DHCP for scanning devices")
                client_list = dhcp_clients

        except (CannotConnect, socket.timeout, OSError):
            self.available = False
            return

        if not client_list and not dhcp_clients:
            return

        # add new clients from client_list
        for mac in client_list:
            if mac not in self.clients:
                self.clients[mac] = MikrotikClient(mac, host=self.host)

        # update all clients
        for mac in self.clients:

            # update dhcp_params if client is in DHCP server
            if dhcp_clients and mac in dhcp_clients:
                self.clients[mac].update(dhcp_params=dhcp_clients[mac])

            # update clients if connected through wireless
            if wireless_clients and mac in wireless_clients:
                self.clients[mac].update(
                    wireless_params=wireless_clients[mac], active=True, host=self.host,
                )
                continue
            # update other clients last_seen if force_dhcp is enabled
            if (
                (self._support_wired or self.force_dhcp)
                and dhcp_clients
                and mac in dhcp_clients
            ):
                active = self.clients[mac].dhcp_params.get("active-address")
                # ping the active devices if arp ping is enabled
                if self.arp_enabled and mac in arp_clients:
                    active = self.do_arp_ping(
                        self.clients[mac].dhcp_params.get("active-address"),
                        arp_clients[mac].get("interface"),
                    )

                self.clients[mac].update(active=active, host=self.host)

    async def async_setup(self):
        """Set up the Mikrotik hub."""
        try:
            await self.hass.async_add_executor_job(self.connect_to_hub)
        except CannotConnect:
            pass
        except LoginError:
            return False

        return True


def get_api(hass, entry):
    """Connect to Mikrotik hub."""
    _LOGGER.debug("Connecting to Mikrotik hub [%s]", entry[CONF_HOST])

    _login_method = (plain, token)
    kwargs = {"login_methods": _login_method, "port": entry[CONF_PORT]}

    if entry[CONF_VERIFY_SSL]:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _ssl_wrapper = ssl_context.wrap_socket
        kwargs["ssl_wrapper"] = _ssl_wrapper

    try:
        api = librouteros.connect(
            entry[CONF_HOST], entry[CONF_USERNAME], entry[CONF_PASSWORD], **kwargs,
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
            raise LoginError
        raise CannotConnect
