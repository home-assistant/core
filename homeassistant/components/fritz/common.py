"""Support for AVM Fritz!Box classes."""
from collections import namedtuple
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

# pylint: disable=import-error
from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus
import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util, get_local_ip

from .const import (
    ATTR_HOST,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    ERROR_CONNECTION_ERROR,
    TRACKER_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

Device = namedtuple("Device", ["mac", "ip", "name"])


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_DEVICES): vol.All(
                        cv.ensure_list,
                        [
                            vol.Schema(
                                {
                                    vol.Optional(CONF_HOST): cv.string,
                                    vol.Optional(CONF_PORT): cv.port,
                                    vol.Required(CONF_USERNAME): cv.string,
                                    vol.Required(CONF_PASSWORD): cv.string,
                                }
                            )
                        ],
                    )
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_HOST): cv.string})


class FritzBoxTools:
    """FrtizBoxTools class."""

    def __init__(
        self,
        hass,
        password,
        username=DEFAULT_USERNAME,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
    ):
        """Initialize FritzboxTools class."""
        self._cancel_scan = None
        self._device_info = None
        self._devices: Dict[str, Any] = {}
        self._unique_id = None
        self.connection = None
        self.error = None
        self.fritzhosts = None
        self.fritzstatus = None
        self.ha_ip = None
        self.hass = hass
        self.host = host
        self.password = password
        self.port = port
        self.success = None
        self.username = username

    async def async_setup(self):
        """Wrap up FritzboxTools class setup."""
        return await self.hass.async_add_executor_job(self.setup)

    def setup(self):
        """Set up FritzboxTools class."""
        try:
            self.connection = FritzConnection(
                address=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                timeout=60.0,
            )

            self.fritzstatus = FritzStatus(fc=self.connection)
            self._unique_id = self.connection.call_action("DeviceInfo:1", "GetInfo")[
                "NewSerialNumber"
            ]
            self.fritzhosts = FritzHosts(fc=self.connection)
            self._device_info = self._fetch_device_info()
            self.success = True
            self.error = False
        except FritzConnectionException:
            self.success = False
            self.error = ERROR_CONNECTION_ERROR

        self.ha_ip = get_local_ip()

        self.scan_devices()

        self._cancel_scan = async_track_time_interval(
            self.hass, self.scan_devices, timedelta(seconds=TRACKER_SCAN_INTERVAL)
        )

        return self.success, self.error

    def unload(self):
        """Unload FritzboxTools class."""
        _LOGGER.debug("Unloading Fritz!Box router integration")
        if self._cancel_scan is not None:
            self._cancel_scan()
            self._cancel_scan = None

    @property
    def unique_id(self):
        """Return unique id."""
        return self._unique_id

    @property
    def fritzbox_model(self):
        """Return model."""
        return self._device_info["model"].replace("FRITZ!Box ", "")

    @property
    def device_info(self):
        """Return device info."""
        return self._device_info

    @property
    def devices(self) -> Dict[str, Any]:
        """Return devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per Fritzbox entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._unique_id}"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Fritzbox entry to signal updates in devices."""
        return f"{DOMAIN}-device-update-{self._unique_id}"

    def _update_info(self):
        """Retrieve latest information from the FRITZ!Box."""
        if not self.success:
            return None

        return self.fritzhosts.get_hosts_info()

    def scan_devices(self, now: Optional[datetime] = None) -> None:
        """Scan for new devices and return a list of found device ids."""

        _LOGGER.debug("Checking devices for Fritz!Box router %s", self.host)

        new_device = False
        for known_host in self._update_info():
            if not known_host.get("mac"):
                continue

            dev_mac = known_host["mac"]
            dev_name = known_host["name"]
            dev_ip = known_host["ip"]
            dev_home = known_host["status"]

            dev_info = Device(dev_mac, dev_ip, dev_name)

            if dev_mac in self._devices:
                self._devices[dev_mac].update(dev_info, dev_home)
            else:
                device = FritzDevice(dev_mac)
                device.update(dev_info, dev_home)
                self._devices[dev_mac] = device
                new_device = True

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    def _fetch_device_info(self):
        """Fetch device info."""
        info = self.connection.call_action("DeviceInfo:1", "GetInfo")
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": info.get("NewModelName"),
            "manufacturer": "AVM",
            "model": info.get("NewModelName"),
            "sw_version": info.get("NewSoftwareVersion"),
        }


class FritzDevice:
    """FritzScanner device."""

    def __init__(self, mac, name=None):
        """Initialize device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info, dev_home):
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()
        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")
        self._connected = dev_home

        if not self._connected:
            self._ip_address = None
        else:
            self._last_activity = utc_point_in_time
            self._ip_address = dev_info.ip

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self):
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self):
        """Get Name."""
        return self._name

    @property
    def ip_address(self):
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity
