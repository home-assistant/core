"""The Mikrotik router class."""

from datetime import timedelta
import ssl
from typing import Any, override

import librouteros
from librouteros.exceptions import ConnectionClosed
from librouteros.login import plain as login_plain, token as login_token

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODEL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ARP,
    ATTR_ROUTERBOARD_FIRMWARE,
    ATTR_SERIAL_NUMBER,
    CAPSMAN,
    CONF_ARP_PING,
    CONF_DETECTION_TIME,
    CONF_FORCE_DHCP,
    DEFAULT_DETECTION_TIME,
    DHCP,
    DOMAIN,
    HEALTH,
    IDENTITY,
    INTERFACE,
    IS_CAPSMAN,
    IS_WIFI,
    IS_WIFIWAVE2,
    IS_WIRELESS,
    LOGGER,
    MIKROTIK_SERVICES,
    NAME,
    PING,
    POE,
    RESOURCE,
    ROUTERBOARD,
    UPDATE,
    WIFI,
    WIFIWAVE2,
    WIRELESS,
)
from .device import Device
from .errors import CannotConnect, LoginError
from .utils import calculate_uptime, mikrotik_config_entry_errors, percentage

type MikrotikConfigEntry = ConfigEntry[MikrotikDataUpdateCoordinator]

CONNECTION_ERRORS = (ConnectionClosed, OSError, TimeoutError)


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
        self.sensors: dict[str, Any] = {}
        self.system: dict[str, Any] = {}
        self.interfaces: list[dict[str, Any]] = []

    def _get_system_details(self, during_setup: bool = False) -> None:
        """Retrieve system and routerboard details from Mikrotik API."""
        self.system[IDENTITY] = (
            self.command(MIKROTIK_SERVICES[IDENTITY], during_setup=during_setup) or [{}]
        )[0]
        self.system[ROUTERBOARD] = (
            self.command(
                MIKROTIK_SERVICES[ROUTERBOARD],
                suppress_errors=True,
                during_setup=during_setup,
            )
            or [{}]
        )[0]

    def _get_health_details(self) -> None:
        """Retrieve health details from Mikrotik API."""
        health_data = (
            self.command(MIKROTIK_SERVICES[HEALTH], suppress_errors=True) or []
        )
        self.sensors[HEALTH] = {
            entry["name"]: entry["value"]
            for entry in health_data
            if "name" in entry and "value" in entry
        }

    def _get_resource_details(self) -> None:
        """Retrieve resource details from Mikrotik API."""
        resource_data = (
            self.command(MIKROTIK_SERVICES[RESOURCE], suppress_errors=True) or [{}]
        )[0]
        self.sensors[RESOURCE] = (
            {
                "cpu-load": resource_data.get("cpu-load"),
                "memory-usage": percentage(
                    resource_data.get("total-memory", 0),
                    resource_data.get("free-memory", 0),
                ),
                "disk-usage": percentage(
                    resource_data.get("total-hdd-space", 0),
                    resource_data.get("free-hdd-space", 0),
                ),
                "uptime": (
                    calculate_uptime(resource_data["uptime"])
                    if resource_data.get("uptime")
                    else None
                ),
            }
            if resource_data
            else {}
        )

    def _get_interfaces_details(self) -> None:
        """Get interfaces details."""
        all_interfs = self.command(MIKROTIK_SERVICES[INTERFACE])

        fields = {
            ".id",
            "name",
            "type",
            "mac-address",
            "running",
            "disabled",
        }

        poe_interfs = self.command(MIKROTIK_SERVICES[POE], suppress_errors=True) or []

        poe_by_id = {
            poe_interf[".id"]: poe_interf.get("poe-out", "off")
            for poe_interf in poe_interfs
        }

        existing_by_id = {interf[".id"]: interf for interf in self.interfaces}

        interfaces = []
        for interf in all_interfs:
            if interf.get("type") == "loopback":
                continue
            data = {key: interf.get(key) for key in fields}
            if (poe_out := poe_by_id.get(data[".id"])) is not None:
                data["poe-out"] = poe_out
            if existing := existing_by_id.get(data[".id"]):
                existing.update(data)
                interfaces.append(existing)
            else:
                interfaces.append(data)

        self.interfaces = interfaces

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
        return self.config_entry.options.get(CONF_ARP_PING, False)  # type: ignore[no-any-return]

    @property
    def force_dhcp(self) -> bool:
        """Return force_dhcp option setting."""
        return self.config_entry.options.get(CONF_FORCE_DHCP, False)  # type: ignore[no-any-return]

    def get_hub_details(self) -> None:
        """Get Hub info."""
        self._get_system_details(during_setup=True)
        self.hostname = str(self.system[IDENTITY].get(NAME))
        self.model = str(self.system[ROUTERBOARD].get(ATTR_MODEL))
        self.firmware = str(self.system[ROUTERBOARD].get(ATTR_ROUTERBOARD_FIRMWARE))
        self.serial_number = str(self.system[ROUTERBOARD].get(ATTR_SERIAL_NUMBER))
        self.support_capsman = bool(
            self.command(
                MIKROTIK_SERVICES[IS_CAPSMAN], suppress_errors=True, during_setup=True
            )
        )
        self.support_wireless = bool(
            self.command(
                MIKROTIK_SERVICES[IS_WIRELESS], suppress_errors=True, during_setup=True
            )
        )
        self.support_wifiwave2 = bool(
            self.command(
                MIKROTIK_SERVICES[IS_WIFIWAVE2],
                suppress_errors=True,
                during_setup=True,
            )
        )
        self.support_wifi = bool(
            self.command(
                MIKROTIK_SERVICES[IS_WIFI], suppress_errors=True, during_setup=True
            )
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
        with mikrotik_config_entry_errors():
            # Retrieve data
            self.all_devices = self.get_list_from_interface(DHCP)

            # A hub can expose more than one wireless stack at once (e.g. the
            # legacy "wireless" package kept for CAPsMAN alongside the newer
            # "wifi" registration table), so merge every supported interface
            # instead of picking only the first match.
            for supported, interface, message in (
                (self.support_capsman, CAPSMAN, "Hub is a CAPSman manager"),
                (self.support_wireless, WIRELESS, "Hub supports wireless Interface"),
                (self.support_wifiwave2, WIFIWAVE2, "Hub supports wifiwave2 Interface"),
                (self.support_wifi, WIFI, "Hub supports wifi Interface"),
            ):
                if supported:
                    LOGGER.debug(message)
                    wireless_devices.update(self.get_list_from_interface(interface))

            device_list = wireless_devices

            if not device_list or self.force_dhcp:
                device_list = self.all_devices
                LOGGER.debug("Falling back to DHCP for scanning devices")

            if self.arp_enabled:
                LOGGER.debug("Using arp-ping to check devices")
                arp_devices = self.get_list_from_interface(ARP)

            # get hub details and system info
            self._get_system_details()

            self.system[UPDATE] = (
                self.command(MIKROTIK_SERVICES[UPDATE], suppress_errors=True) or [{}]
            )[0]

            self._get_health_details()
            self._get_resource_details()
            self._get_interfaces_details()

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
        LOGGER.debug("pinging - %s", ip_address)
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": ip_address,
        }
        data = self.command(MIKROTIK_SERVICES[PING], params)
        if data:
            status = 0
            for result in data:
                if "status" in result:
                    status += 1
            if status == len(data):
                LOGGER.debug(
                    "Mikrotik %s - %s arp_ping timed out", ip_address, interface
                )
                return False
        return True

    def command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        suppress_errors: bool = False,
        during_setup: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve data from Mikrotik API."""
        LOGGER.debug("Running command %s", cmd)
        with mikrotik_config_entry_errors(
            suppress_errors=suppress_errors, during_setup=during_setup
        ):
            try:
                if params:
                    return list(self.api(cmd, **params))
                return list(self.api(cmd))
            except CONNECTION_ERRORS as err:
                LOGGER.debug(
                    "Mikrotik %s - connection dropped (%s), reconnecting",
                    self._host,
                    err,
                )
                self.api = get_api(dict(self.config_entry.data))
                if params:
                    return list(self.api(cmd, **params))
                return list(self.api(cmd))


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
            LOGGER,
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

    @override
    async def _async_update_data(self) -> None:
        """Update Mikrotik devices information."""
        await self.hass.async_add_executor_job(self._mk_data.update_devices)


def get_api(entry: dict[str, Any]) -> librouteros.Api:
    """Connect to Mikrotik hub."""
    LOGGER.debug("Connecting to Mikrotik hub [%s]", entry[CONF_HOST])

    kwargs = {"port": entry["port"], "encoding": "utf8"}

    if entry[CONF_VERIFY_SSL]:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _ssl_wrapper = ssl_context.wrap_socket
        kwargs["ssl_wrapper"] = _ssl_wrapper

    _error: Exception | None = None
    for method in (login_plain, login_token):
        try:
            kwargs["login_method"] = method
            api = librouteros.connect(
                entry[CONF_HOST],
                entry[CONF_USERNAME],
                entry[CONF_PASSWORD],
                **kwargs,
            )
            _error = None
            break
        except (
            librouteros.exceptions.LibRouterosError,
            OSError,
            TimeoutError,
        ) as api_error:
            _error = api_error

    if _error is not None:
        LOGGER.debug("Mikrotik %s error: %s", entry[CONF_HOST], _error)
        if "invalid user name or password" in str(_error):
            raise LoginError from _error
        raise CannotConnect from _error

    LOGGER.debug("Connected to %s successfully", entry[CONF_HOST])
    return api
