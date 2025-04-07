"""The Mikrotik router class."""

from __future__ import annotations

from datetime import timedelta
import logging
import ssl
from typing import Any

import librouteros
from librouteros.login import plain as login_plain, token as login_token

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ARP,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    CAPSMAN,
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_DETECTION_TIME,
    DHCP,
    DOMAIN,
    IDENTITY,
    INFO,
    IS_CAPSMAN,
    IS_WIFI,
    IS_WIFIWAVE2,
    IS_WIRELESS,
    MIKROTIK_SERVICES,
    NAME,
    WIFI,
    WIFIWAVE2,
    WIRELESS,
)
from .device import Device
from .errors import CannotConnect, LoginError

_LOGGER = logging.getLogger(__name__)

type MikrotikConfigEntry = ConfigEntry[MikrotikDataUpdateCoordinator]


class MikrotikData:
    """Handle all communication with the Mikrotik API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: librouteros.Api
    ) -> None:
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        self._host: str = self.config_entry.data[CONF_HOST]
        self.all_devices: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, Device] = {}
        self.support_capsman: bool = False
        self.support_wireless: bool = False
        self.support_wifiwave2: bool = False
        self.support_wifi: bool = False
        self.hostname: str = ""
        self.model: str = ""
        self.firmware: str = ""
        self.serial_number: str = ""

    @staticmethod
    def load_mac(devices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Load dictionary using MAC address as key."""
        mac_devices = {}
        for device in devices:
            if "mac-address" in device:
                mac = device["mac-address"]
                mac_devices[mac] = device
        return mac_devices

    @property
    def arp_enabled(self) -> bool:
        """Return arp_ping option setting."""
        return self.config_entry.options.get(CONF_ARP_PING, False)

    @property
    def force_dhcp(self) -> bool:
        """Return force_dhcp option setting."""
        return self.config_entry.options.get(CONF_FORCE_DHCP, False)

    def get_info(self, param: str) -> str:
        """Return device model name."""
        cmd = IDENTITY if param == NAME else INFO
        if data := self.command(MIKROTIK_SERVICES[cmd], suppress_errors=(cmd == INFO)):
            return str(data[0].get(param))
        return ""

    def get_hub_details(self) -> None:
        """Get Hub info."""
        self.hostname = self.get_info(NAME)
        self.model = self.get_info(ATTR_MODEL)
        self.firmware = self.get_info(ATTR_FIRMWARE)
        self.serial_number = self.get_info(ATTR_SERIAL_NUMBER)
        self.support_capsman = bool(
            self.command(MIKROTIK_SERVICES[IS_CAPSMAN], suppress_errors=True)
        )
        self.support_wireless = bool(
            self.command(MIKROTIK_SERVICES[IS_WIRELESS], suppress_errors=True)
        )
        self.support_wifiwave2 = bool(
            self.command(MIKROTIK_SERVICES[IS_WIFIWAVE2], suppress_errors=True)
        )
        self.support_wifi = bool(
            self.command(MIKROTIK_SERVICES[IS_WIFI], suppress_errors=True)
        )

    def get_list_from_interface(self, interface: str) -> dict[str, dict[str, Any]]:
        """Get devices from interface."""
        if result := self.command(MIKROTIK_SERVICES[interface]):
            return self.load_mac(result)
        return {}

    def restore_device(self, mac: str) -> None:
        """Restore a missing device after restart."""
        self.devices[mac] = Device(mac, self.all_devices[mac])

    def update_devices(self) -> None:
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
            elif self.support_wifiwave2:
                _LOGGER.debug("Hub supports wifiwave2 Interface")
                device_list = wireless_devices = self.get_list_from_interface(WIFIWAVE2)
            elif self.support_wifi:
                _LOGGER.debug("Hub supports wifi Interface")
                device_list = wireless_devices = self.get_list_from_interface(WIFI)

            if not device_list or self.force_dhcp:
                device_list = self.all_devices
                _LOGGER.debug("Falling back to DHCP for scanning devices")

            if self.arp_enabled:
                _LOGGER.debug("Using arp-ping to check devices")
                arp_devices = self.get_list_from_interface(ARP)

            # get new hub firmware version if updated
            self.firmware = self.get_info(ATTR_FIRMWARE)

        except CannotConnect as err:
            raise UpdateFailed from err
        except LoginError as err:
            raise ConfigEntryAuthFailed from err

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
                    str(params.get("active-address")),
                    str(arp_devices[mac].get("interface")),
                )
            self.devices[mac].update(active=active)

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
        cmd = "/ping"
        data = self.command(cmd, params)
        if data:
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

    def command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        suppress_errors: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve data from Mikrotik API."""
        _LOGGER.debug("Running command %s", cmd)
        try:
            if params:
                return list(self.api(cmd=cmd, **params))
            return list(self.api(cmd=cmd))
        except (
            librouteros.exceptions.ConnectionClosed,
            OSError,
            TimeoutError,
        ) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
            # try to reconnect
            self.api = get_api(dict(self.config_entry.data))
            # we still have to raise CannotConnect to fail the update.
            raise CannotConnect from api_error
        except librouteros.exceptions.ProtocolError as api_error:
            emsg = "Mikrotik %s failed to retrieve data. cmd=[%s] Error: %s"
            if suppress_errors and "no such command prefix" in str(api_error):
                _LOGGER.debug(emsg, self._host, cmd, api_error)
                return []
            _LOGGER.warning(emsg, self._host, cmd, api_error)
            return []


class MikrotikDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Mikrotik Hub Object."""

    config_entry: MikrotikConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MikrotikConfigEntry,
        api: librouteros.Api,
    ) -> None:
        """Initialize the Mikrotik Client."""
        self._mk_data = MikrotikData(hass, config_entry, api)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=10),
        )

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return str(self.config_entry.data[CONF_HOST])

    @property
    def hostname(self) -> str:
        """Return the hostname of the hub."""
        return self._mk_data.hostname

    @property
    def model(self) -> str:
        """Return the model of the hub."""
        return self._mk_data.model

    @property
    def firmware(self) -> str:
        """Return the firmware of the hub."""
        return self._mk_data.firmware

    @property
    def serial_num(self) -> str:
        """Return the serial number of the hub."""
        return self._mk_data.serial_number

    @property
    def option_detection_time(self) -> timedelta:
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def api(self) -> MikrotikData:
        """Represent Mikrotik data object."""
        return self._mk_data

    async def _async_update_data(self) -> None:
        """Update Mikrotik devices information."""
        await self.hass.async_add_executor_job(self._mk_data.update_devices)


def get_api(entry: dict[str, Any]) -> librouteros.Api:
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
    except (
        librouteros.exceptions.LibRouterosError,
        OSError,
        TimeoutError,
    ) as api_error:
        _LOGGER.error("Mikrotik %s error: %s", entry[CONF_HOST], api_error)
        if "invalid user name or password" in str(api_error):
            raise LoginError from api_error
        raise CannotConnect from api_error

    _LOGGER.debug("Connected to %s successfully", entry[CONF_HOST])
    return api
