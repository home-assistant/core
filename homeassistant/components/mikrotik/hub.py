"""The mikrotik router class."""
from datetime import timedelta
import logging
import ssl

import librouteros
from librouteros.login import login_plain, login_token

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
    CONF_TRACK_DEVICES,
    DEFAULT_DETECTION_TIME,
    DHCP,
    IDENTITY,
    INFO,
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
        self.support_wireless = bool(self.command(MIKROTIK_SERVICES[IS_WIRELESS]))

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

    def connect_to_hub(self):
        """Connect to hub."""
        try:
            self.api = get_hub(self.hass, self.config_entry.data)
            self.available = True
            return True
        except (LoginError, CannotConnect):
            self.available = False
            return False

    def get_list_from_interface(self, interface):
        """Get devices from interface."""
        result = self.command(MIKROTIK_SERVICES[interface])
        return self.load_mac(result) if result else None

    def restore_device(self, mac):
        """Restore a missing device after restart."""
        self.devices[mac] = Device(mac, self.all_devices[mac])

    def update_devices(self):
        """Get list of devices with latest status."""
        arp_devices = {}
        wireless_devices = {}
        device_list = {}
        try:
            self.all_devices = self.get_list_from_interface(DHCP)
            if self.support_wireless:
                _LOGGER.debug("wireless is supported")
                for interface in [CAPSMAN, WIRELESS]:
                    wireless_devices = self.get_list_from_interface(interface)
                    if wireless_devices:
                        _LOGGER.debug("Scanning wireless devices using %s", interface)
                        break

            if self.support_wireless and not self.force_dhcp:
                device_list = wireless_devices
            else:
                device_list = self.all_devices
                _LOGGER.debug("Falling back to DHCP for scanning devices")

            if self.arp_enabled:
                arp_devices = self.get_list_from_interface(ARP)

        except CannotConnect:
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
            if params:
                response = self.api(cmd=cmd, **params)
            else:
                response = self.api(cmd=cmd)
        except (librouteros.exceptions.ConnectionError,) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
            raise CannotConnect
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
        ) as api_error:
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
        return self._mk_data.get_info(NAME)

    @property
    def model(self):
        """Return the model of the hub."""
        return self._mk_data.get_info(ATTR_MODEL)

    @property
    def firmware(self):
        """Return the firware of the hub."""
        return self._mk_data.get_info(ATTR_FIRMWARE)

    @property
    def serial_num(self):
        """Return the serial number of the hub."""
        return self._mk_data.get_info(ATTR_SERIAL_NUMBER)

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

    async def add_options(self):
        """Populate default options for Mikrotik."""
        if not self.config_entry.options:
            hub_options = self.config_entry.data.pop("options", {})
            system_options = {
                "disable_new_entities": not hub_options.get(CONF_TRACK_DEVICES, False)
            }
            if CONF_DETECTION_TIME in hub_options:
                detection_time = hub_options[CONF_DETECTION_TIME].seconds
            else:
                detection_time = DEFAULT_DETECTION_TIME
            options = {
                CONF_ARP_PING: hub_options.get(CONF_ARP_PING, False),
                CONF_FORCE_DHCP: hub_options.get(CONF_FORCE_DHCP, False),
                CONF_DETECTION_TIME: detection_time,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options, system_options=system_options
            )

    async def request_update(self):
        """Request an update."""
        if self.progress is not None:
            return await self.progress

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
                get_hub, self.hass, self.config_entry.data
            )
        except CannotConnect:
            raise ConfigEntryNotReady
        except LoginError:
            return False

        self._mk_data = MikrotikData(self.hass, self.config_entry, api)
        await self.add_options()
        await self.hass.async_add_executor_job(self._mk_data.update_devices)
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "device_tracker"
            )
        )
        return True


def get_hub(hass, config_entry):
    """Connect to Mikrotik hub."""
    _LOGGER.debug("Connecting to Mikrotik hub [%s]", config_entry[CONF_HOST])

    _login_method = (login_plain, login_token)
    kwargs = {"login_methods": _login_method, "port": config_entry["port"]}

    if config_entry[CONF_VERIFY_SSL]:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _ssl_wrapper = ssl_context.wrap_socket
        kwargs["ssl_wrapper"] = _ssl_wrapper

    try:
        api = librouteros.connect(
            config_entry[CONF_HOST],
            config_entry[CONF_USERNAME],
            config_entry[CONF_PASSWORD],
            **kwargs,
        )
        _LOGGER.debug("Connected to %s successfully", config_entry[CONF_HOST])
        return api
    except (
        librouteros.exceptions.TrapError,
        librouteros.exceptions.MultiTrapError,
        librouteros.exceptions.ConnectionError,
    ) as api_error:
        _LOGGER.error("Mikrotik %s error: %s", config_entry[CONF_HOST], api_error)
        if "invalid user name or password" in str(api_error):
            raise LoginError
        raise CannotConnect
