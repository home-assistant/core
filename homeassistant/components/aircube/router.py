"""The airCube router class."""
from datetime import timedelta
import json
import logging
import socket

import requests

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import ATTR_DEVICE_TRACKER, CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
from .errors import CannotConnect, ConnectionTimeout, LoginError, SSLError

_LOGGER = logging.getLogger(__name__)


class Device:
    """Represents a network device."""

    def __init__(self, mac, params):
        """Initialize the network device."""
        _LOGGER.debug("initialize Device")
        self._mac = mac
        self._params = params
        self._last_seen = None
        self._attrs = {}

    @property
    def name(self):
        """Return device name."""
        return self._mac

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
        attr_data = self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]
        return self._attrs

    def update(self, params=None, active=False):
        """Update Device params."""
        if params:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()


class AirCubeData:
    """Handle all communication with the airCube API."""

    def __init__(self, hass, config_entry, api):
        """Initialize the airCube Client."""
        _LOGGER.debug("initialize AirCubeData")
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self._host = self.config_entry.data[CONF_HOST]
        self.all_devices = {}
        self.devices = {}
        self.available = True
        self.hostname = None
        self.model = None
        self.firmware = None
        self.serial_number = None

    @property
    def host(self):
        """Return the host of this router."""
        return self.config_entry.data[CONF_HOST]

    @property
    def url(self):
        """Return the url of this router."""
        return f"https://{self.host}/ubus"

    @property
    def username(self):
        """Return the username for this router."""
        return self.config_entry.data[CONF_USERNAME]

    @property
    def password(self):
        """Return the password for this router."""
        return self.config_entry.data[CONF_PASSWORD]

    @property
    def verify_ssl(self):
        """Return the ssl verification setting for this router."""
        return self.config_entry.data[CONF_VERIFY_SSL]

    @staticmethod
    def load_mac(devices=None):
        """Load dictionary using MAC address as key."""
        if not devices:
            return None
        mac_devices = {}
        for device in devices:
            mac_pretty = slugify(device)
            mac_devices[mac_pretty] = device
        return mac_devices

    def get_info(self, param):
        """Return device model name."""
        data = self.command()
        return data if data else None

    def get_router_details(self):
        """Get router info."""
        data = self.command()
        self.hostname = data["result"][1]["results"]["system"]["board"]["hostname"]
        self.model = data["result"][1]["results"]["system"]["board"]["model"]
        self.firmware = data["result"][1]["results"]["system"]["board"]["release"][
            "version"
        ]
        self.serial_number = data["result"][1]["results"]["system"]["board"]["macaddr"]

    def connect_to_router(self):
        """Connect to router."""
        try:
            self.api = get_api(
                self.hass, self.url, self.username, self.password, self.verify_ssl
            )
            self.available = True
            return True
        except (LoginError, CannotConnect):
            self.available = False
            return False

    def get_list_from_interface(self):
        """Get devices from interface."""
        last_results = []
        result = self.command()
        mac_data0 = result["result"][1]["results"]["wireless"]["interface"]["wlan0"][
            "assoclist"
        ]
        for i in mac_data0:
            last_results.append(i["mac"])
        # Only airCube AC has 5GHz radio
        try:
            mac_data1 = result["result"][1]["results"]["wireless"]["interface"][
                "wlan1"
            ]["assoclist"]
            for i in mac_data1:
                last_results.append(i["mac"])
        except KeyError:
            pass
        return self.load_mac(last_results) if last_results else {}

    def restore_device(self, mac):
        """Restore a missing device after restart."""
        self.devices[mac] = Device(mac, self.all_devices[mac])

    def update_devices(self):
        """Get list of devices with latest status."""
        device_list = {}
        try:
            self.all_devices = self.get_list_from_interface()
            device_list = self.all_devices

        except (CannotConnect):
            self.available = False
            return

        if not device_list:
            return

        _LOGGER.debug("device_list: %s", device_list)

        for mac, params in device_list.items():  # pylint: disable=unused-variable
            if mac not in self.devices:
                self.devices[mac] = Device(mac, self.all_devices.get(mac, {}))
            else:
                self.devices[mac].update(params=self.all_devices.get(mac, {}))

            active = True
            self.devices[mac].update(active=active)

    def command(self):
        """Retrieve data from airCube API."""
        try:
            _LOGGER.debug("Running airCube api.")
            response = get_api(
                self.hass, self.url, self.username, self.password, self.verify_ssl
            )
        except CannotConnect:
            _LOGGER.error("Error connecting to the router.")
            raise CannotConnect

        return response if response else None

    def update(self):
        """Update device_tracker from airCube API."""
        if not self.available or not self.api:
            if not self.connect_to_router():
                return
        _LOGGER.debug("updating network devices for host: %s", self._host)
        self.update_devices()


class AirCubeRouter:
    """airCube Router Object."""

    def __init__(self, hass, config_entry):
        """Initialize the airCube Client."""
        _LOGGER.debug("initialize AirCubeRouter")
        self.hass = hass
        self.config_entry = config_entry
        self._ac_data = None
        self.progress = None

    @property
    def host(self):
        """Return the host of this router."""
        return self.config_entry.data[CONF_HOST]

    @property
    def url(self):
        """Return the url of this router."""
        return f"https://{self.host}/ubus"

    @property
    def username(self):
        """Return the username for this router."""
        return self.config_entry.data[CONF_USERNAME]

    @property
    def password(self):
        """Return the password for this router."""
        return self.config_entry.data[CONF_PASSWORD]

    @property
    def verify_ssl(self):
        """Return the ssl verification setting for this router."""
        return self.config_entry.data[CONF_VERIFY_SSL]

    @property
    def hostname(self):
        """Return the hostname of the router."""
        return self._ac_data.hostname

    @property
    def model(self):
        """Return the model of the router."""
        return self._ac_data.model

    @property
    def firmware(self):
        """Return the firmware of the router."""
        return self._ac_data.firmware

    @property
    def serial_num(self):
        """Return the serial number of the router."""
        return self._ac_data.serial_number

    @property
    def available(self):
        """Return if the router is connected."""
        return self._ac_data.available

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(seconds=self.config_entry.options[CONF_DETECTION_TIME])

    @property
    def signal_update(self):
        """Event specific per airCube entry to signal updates."""
        return f"aircube-update-{self.host}"

    @property
    def api(self):
        """Represent airCube data object."""
        return self._ac_data

    async def async_add_options(self):
        """Populate default options for airCube."""
        if not self.config_entry.options:
            options = {
                CONF_DETECTION_TIME: self.config_entry.data.pop(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
                ),
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
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
        """Update airCube devices information."""
        await self.hass.async_add_executor_job(self._ac_data.update)
        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up the airCube router."""
        try:
            api = await self.hass.async_add_executor_job(
                get_api,
                self.hass,
                self.url,
                self.username,
                self.password,
                self.verify_ssl,
            )
        except IndexError:
            _LOGGER.error("Error connecting to the router.")
            raise CannotConnect

        self._ac_data = AirCubeData(self.hass, self.config_entry, api)
        await self.async_add_options()
        await self.hass.async_add_executor_job(self._ac_data.get_router_details)
        await self.hass.async_add_executor_job(self._ac_data.update)

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "device_tracker"
            )
        )
        return True


def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, verify_ssl, **params):
    """Perform one JSON RPC operation."""
    _LOGGER.debug("Requesting json rpc for airCube router.")

    data = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": rpcmethod,
            "params": [session_id, subsystem, method, params],
        }
    )

    try:
        res = requests.post(url, data=data, timeout=5, verify=verify_ssl)
    except (requests.exceptions.ConnectTimeout, socket.timeout):
        _LOGGER.error("Connection to router timed out. Check host.")
        raise ConnectionTimeout
    except (requests.exceptions.SSLError):
        _LOGGER.error("SSL error.")
        raise SSLError
    except (requests.exceptions.ConnectionError):
        _LOGGER.error("Error connecting to the router.")
        raise CannotConnect
    else:
        return res.json()


def _get_session_id(url, username, password, verify_ssl):
    """Get the authentication token for the given host+username+password."""
    res = []

    try:
        res = _req_json_rpc(
            url,
            "00000000000000000000000000000000",
            "call",
            "session",
            "login",
            verify_ssl=verify_ssl,
            username=username,
            password=password,
        )
    finally:
        pass
    if res is not None:
        try:
            res["result"][1]["ubus_rpc_session"]
        except LookupError:
            _LOGGER.error("Login unsuccessful. Check credentials.")
            raise LoginError
        return res["result"][1]["ubus_rpc_session"]


def get_api(hass, url, username, password, verify_ssl):
    """Connect to airCube router."""
    _LOGGER.debug("Connecting to airCube router.")

    session_id = None
    if session_id is None:
        session_id = _get_session_id(url, username, password, verify_ssl)

    api = _req_json_rpc(url, session_id, "call", "ubnt", "stats", verify_ssl)

    if not api["result"][1]["results"]:
        session_id = _get_session_id(url, username, password, verify_ssl)
        api = _req_json_rpc(url, session_id, "call", "ubnt", "stats", verify_ssl)
        if not api["result"][1]["results"]:
            _LOGGER.error("Login unsuccessful. Check credentials.")
            raise LoginError
    return api
