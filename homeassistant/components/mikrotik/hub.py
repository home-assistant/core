"""The Mikrotik router class."""
from datetime import timedelta
import logging
import socket
import ssl

import librouteros
from librouteros.login import plain as login_plain, token as login_token

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
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
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_DETECTION_TIME,
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


class Device:
    """Represents a network device."""

    def __init__(self, mac, params):
        """Initialize the network device."""
        self._mac = mac
        self._params = params
        self._last_seen = None
        self._attrs = {}
        self._wireless_params = None

    @property
    def name(self):
        """Return device name."""
        return self._params.get("host-name", self.mac)

    @property
    def mac(self):
        """Return device mac."""
        return self._mac

    @property
    def last_seen(self):
        """Return device last seen."""
        return self._last_seen

    @property
    def attrs(self):
        """Return device attributes."""
        attr_data = self._wireless_params if self._wireless_params else self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]
        self._attrs["ip_address"] = self._params.get("active-address")
        return self._attrs

    def update(self, wireless_params=None, params=None, active=False):
        """Update Device params."""
        if wireless_params:
            self._wireless_params = wireless_params
        if params:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()


class MikrotikData:
    """Handle all communication with the Mikrotik API."""

    def __init__(self, hass, config_entry, api):
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self._host = self.config_entry.data[CONF_HOST]
        self.all_devices = {}
        self.devices = {}
        self.available = True
        self.support_capsman = False
        self.support_wireless = False
        self.hostname = None
        self.model = None
        self.firmware = None
        self.serial_number = None

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

    @property
    def arp_enabled(self):
        """Return arp_ping option setting."""
        return self.config_entry.options[CONF_ARP_PING]

    @property
    def force_dhcp(self):
        """Return force_dhcp option setting."""
        return self.config_entry.options[CONF_FORCE_DHCP]

    def get_info(self, param):
        """Return device model name."""
        cmd = IDENTITY if param == NAME else INFO
        data = self.command(MIKROTIK_SERVICES[cmd])
        return data[0].get(param) if data else None

    def get_hub_details(self):
        """Get Hub info."""
        self.hostname = self.get_info(NAME)
        self.model = self.get_info(ATTR_MODEL)
        self.firmware = self.get_info(ATTR_FIRMWARE)
        self.serial_number = self.get_info(ATTR_SERIAL_NUMBER)
        self.support_capsman = bool(self.command(MIKROTIK_SERVICES[IS_CAPSMAN]))
        self.support_wireless = bool(self.command(MIKROTIK_SERVICES[IS_WIRELESS]))

    def connect_to_hub(self):
        """Connect to hub."""
        try:
            self.api = get_api(self.hass, self.config_entry.data)
            self.available = True
            return True
        except (LoginError, CannotConnect):
            self.available = False
            return False

    def get_list_from_interface(self, interface):
        """Get devices from interface."""
        result = self.command(MIKROTIK_SERVICES[interface])
        return self.load_mac(result) if result else {}

    def restore_device(self, mac):
        """Restore a missing device after restart."""
        self.devices[mac] = Device(mac, self.all_devices[mac])

    def update_devices(self):
        """Get list of devices with latest status."""
        arp_devices = {}
        device_list = {}
        wireless_devices = {}
        try:
            self.all_devices = self.get_list_from_interface(DHCP)
            if self.support_capsman:
                _LOGGER.debug("Hub is a CAPSman manager")
                device_list = wireless_devices = self.get_list_from_interface(CAPSMAN)
            elif self.support_wireless:
                _LOGGER.debug("Hub supports wireless Interface")
                device_list = wireless_devices = self.get_list_from_interface(WIRELESS)

            if not device_list or self.force_dhcp:
                device_list = self.all_devices
                _LOGGER.debug("Falling back to DHCP for scanning devices")

            if self.arp_enabled:
                _LOGGER.debug("Using arp-ping to check devices")
                arp_devices = self.get_list_from_interface(ARP)

            # get new hub firmware version if updated
            self.firmware = self.get_info(ATTR_FIRMWARE)

        except (CannotConnect, socket.timeout, socket.error):
            self.available = False
            return

        if not device_list:
            return

        for mac, params in device_list.items():
            if mac not in self.devices:
                self.devices[mac] = Device(mac, self.all_devices.get(mac, {}))
            else:
                self.devices[mac].update(params=self.all_devices.get(mac, {}))

            if mac in wireless_devices:
                # if wireless is supported then wireless_params are params
                self.devices[mac].update(
                    wireless_params=wireless_devices[mac], active=True
                )
                continue
            # for wired devices or when forcing dhcp check for active-address
            if not params.get("active-address"):
                self.devices[mac].update(active=False)
                continue
            # ping check the rest of active devices if arp ping is enabled
            active = True
            if self.arp_enabled and mac in arp_devices:
                active = self.do_arp_ping(
                    params.get("active-address"), arp_devices[mac].get("interface")
                )
            self.devices[mac].update(active=active)

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
            _LOGGER.info("Running command %s", cmd)
            if params:
                response = list(self.api(cmd=cmd, **params))
            else:
                response = list(self.api(cmd=cmd))
        except (
            librouteros.exceptions.ConnectionClosed,
            socket.error,
            socket.timeout,
        ) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
            raise CannotConnect
        except librouteros.exceptions.ProtocolError as api_error:
            _LOGGER.warning(
                "Mikrotik %s failed to retrieve data. cmd=[%s] Error: %s",
                self._host,
                cmd,
                api_error,
            )
            return None

        return response if response else None

    def update(self):
        """Update device_tracker from Mikrotik API."""
        if not self.available or not self.api:
            if not self.connect_to_hub():
                return
        _LOGGER.debug("updating network devices for host: %s", self._host)
        self.update_devices()


class MikrotikHub:
    """Mikrotik Hub Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry = config_entry
        self._mk_data = None
        self.progress = None

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data[CONF_HOST]

    @property
    def hostname(self):
        """Return the hostname of the hub."""
        return self._mk_data.hostname

    @property
    def model(self):
        """Return the model of the hub."""
        return self._mk_data.model

    @property
    def firmware(self):
        """Return the firmware of the hub."""
        return self._mk_data.firmware

    @property
    def serial_num(self):
        """Return the serial number of the hub."""
        return self._mk_data.serial_number

    @property
    def available(self):
        """Return if the hub is connected."""
        return self._mk_data.available

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(seconds=self.config_entry.options[CONF_DETECTION_TIME])

    @property
    def signal_update(self):
        """Event specific per Mikrotik entry to signal updates."""
        return f"mikrotik-update-{self.host}"

    @property
    def api(self):
        """Represent Mikrotik data object."""
        return self._mk_data

    async def async_add_options(self):
        """Populate default options for Mikrotik."""
        if not self.config_entry.options:
            data = dict(self.config_entry.data)
            options = {
                CONF_ARP_PING: data.pop(CONF_ARP_PING, False),
                CONF_FORCE_DHCP: data.pop(CONF_FORCE_DHCP, False),
                CONF_DETECTION_TIME: data.pop(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                ),
            }

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
        """Update Mikrotik devices information."""
        await self.hass.async_add_executor_job(self._mk_data.update)
        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up the Mikrotik hub."""
        try:
            api = await self.hass.async_add_executor_job(
                get_api, self.hass, self.config_entry.data
            )
        except CannotConnect:
            raise ConfigEntryNotReady
        except LoginError:
            return False

        self._mk_data = MikrotikData(self.hass, self.config_entry, api)
        await self.async_add_options()
        await self.hass.async_add_executor_job(self._mk_data.get_hub_details)
        await self.hass.async_add_executor_job(self._mk_data.update)

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "device_tracker"
            )
        )
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
