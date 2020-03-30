"""The Mikrotik router class."""
import logging
import socket
import ssl

import librouteros
from librouteros.login import plain as login_plain, token as login_token

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ARP,
    ATTR_DEVICE_TRACKER,
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
from .errors import CannotConnect, LoginError

_LOGGER = logging.getLogger(__name__)


class MikrotikClient:
    """Represents a network client."""

    def __init__(self, mac, params, hub_id):
        """Initialize the client."""
        self._mac = mac
        self._params = params
        self._last_seen = None
        self._attrs = {}
        self._wireless_params = None
        self.hub_id = hub_id

    @property
    def name(self):
        """Return client name."""
        return self._params.get("host-name", self.mac)

    @property
    def mac(self):
        """Return client mac."""
        return self._mac

    @property
    def last_seen(self):
        """Return client last seen."""
        return self._last_seen

    @property
    def attrs(self):
        """Return client attributes."""
        attr_data = self._wireless_params if self._wireless_params else self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]
        self._attrs["ip_address"] = self._params.get("active-address")
        return self._attrs

    def update(self, wireless_params=None, params=None, active=False, hub_id=None):
        """Update client params."""
        if hub_id:
            self.hub_id = hub_id
        if wireless_params:
            self._wireless_params = wireless_params
        if params:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()


class MikrotikHub:
    """Represent Mikrotik hub."""

    def __init__(self, hass, config_entry, hub, clients):
        """Initialize the Mikrotik hub."""
        self.hass = hass
        self.data = config_entry.data[CONF_HUBS][hub]
        self.config_entry = config_entry
        self.api = None
        self.all_clients = {}
        self.clients = clients
        self.available = False
        self.support_capsman = False
        self.support_wireless = False
        self._hostname = None
        self._model = None
        self._firmware = None
        self._serial_number = None

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
        return self._model

    @property
    def firmware(self):
        """Return the firmware of the hub."""
        return self._firmware

    @property
    def serial_number(self):
        """Return the serial number of the hub."""
        return self._serial_number

    @property
    def arp_enabled(self):
        """Return arp_ping option setting."""
        return self.config_entry.options[CONF_ARP_PING]

    @property
    def force_dhcp(self):
        """Return force_dhcp option setting."""
        return self.config_entry.options[CONF_FORCE_DHCP]

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

    def get_info(self, param):
        """Return param details."""
        cmd = IDENTITY if param == NAME else INFO
        data = self.command(MIKROTIK_SERVICES[cmd])
        return data[0].get(param) if data else None

    def get_list_from_interface(self, interface):
        """Return clients from interface."""
        result = self.command(MIKROTIK_SERVICES[interface])
        return self.load_mac(result) if result else {}

    def get_hub_details(self):
        """Get hub info."""
        self._hostname = self.get_info(NAME)
        self._model = self.get_info(ATTR_MODEL)
        self._firmware = self.get_info(ATTR_FIRMWARE)
        self._serial_number = self.get_info(ATTR_SERIAL_NUMBER)
        self.support_capsman = bool(self.command(MIKROTIK_SERVICES[IS_CAPSMAN]))
        self.support_wireless = bool(self.command(MIKROTIK_SERVICES[IS_WIRELESS]))

    def connect_to_hub(self):
        """Connect to hub."""
        try:
            self.api = get_api(self.hass, self.data)
            self.get_hub_details()
            self.available = True
        except CannotConnect:
            self.available = False
        except LoginError:
            self.available = False
            return False
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
        try:
            _LOGGER.debug("Running command %s", cmd)
            if params:
                response = list(self.api(cmd=cmd, **params))
            else:
                response = list(self.api(cmd=cmd))
        except (
            librouteros.exceptions.ConnectionClosed,
            socket.error,
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

        return response if response else None

    def update_clients(self):
        """Update clients with latest status."""
        if not self.available or not self.api:
            self.connect_to_hub()
            if not self.available:
                return

        _LOGGER.debug("updating network clients for host: %s", self.host)
        arp_devices = {}
        client_list = {}
        wireless_devices = {}

        try:
            self.all_clients = self.get_list_from_interface(DHCP)
            if self.support_capsman:
                _LOGGER.debug("Hub is a CAPSman manager")
                client_list = wireless_devices = self.get_list_from_interface(CAPSMAN)
            elif self.support_wireless:
                _LOGGER.debug("Hub supports wireless Interface")
                client_list = wireless_devices = self.get_list_from_interface(WIRELESS)

            if not client_list or self.force_dhcp:
                client_list = self.all_clients
                _LOGGER.debug("Falling back to DHCP for scanning devices")

            if self.arp_enabled:
                _LOGGER.debug("Using arp-ping to check devices")
                arp_devices = self.get_list_from_interface(ARP)

        except (CannotConnect, socket.timeout, socket.error):
            self.available = False
            return

        if not client_list:
            return

        for mac, params in client_list.items():

            if mac not in self.clients:
                self.clients[mac] = MikrotikClient(
                    mac, self.all_clients.get(mac, {}), self.serial_number
                )
            else:
                self.clients[mac].update(
                    params=self.all_clients.get(mac, {}), hub_id=self.serial_number
                )

            if mac in wireless_devices:
                # if wireless is supported then wireless_params are params
                self.clients[mac].update(
                    wireless_params=wireless_devices[mac], active=True
                )
                continue
            # for wired devices or when forcing dhcp check for active-address
            if not params.get("active-address"):
                self.clients[mac].update(active=False)
                continue
            # ping check the rest of active devices if arp ping is enabled
            active = True
            if self.arp_enabled and mac in arp_devices:
                active = self.do_arp_ping(
                    params.get("active-address"), arp_devices[mac].get("interface")
                )
            self.clients[mac].update(active=active)

    async def async_setup(self):
        """Set up the Mikrotik hub."""
        if not await self.hass.async_add_executor_job(self.connect_to_hub):
            return False

        return True


def get_api(hass, entry):
    """Connect to Mikrotik hub."""
    _LOGGER.debug("Connecting to Mikrotik hub [%s]", entry[CONF_HOST])

    _login_method = (login_plain, login_token)
    kwargs = {"login_methods": _login_method, "port": entry["port"]}

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
        socket.error,
        socket.timeout,
    ) as api_error:
        _LOGGER.error("Mikrotik %s error: %s", entry[CONF_HOST], api_error)
        if "invalid user name or password" in str(api_error):
            raise LoginError
        raise CannotConnect
