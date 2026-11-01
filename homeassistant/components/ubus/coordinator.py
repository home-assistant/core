"""DataUpdateCoordinator for the OpenWrt (ubus) integration."""

from datetime import timedelta
import logging
from typing import override

from openwrt.ubus import Ubus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DHCP_SOFTWARE, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type UbusConfigEntry = ConfigEntry[UbusDataUpdateCoordinator]


class UbusDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str | None]]):
    """Fetch the authorized wireless clients from an OpenWrt router over ubus."""

    config_entry: UbusConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: UbusConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        self.host: str = config_entry.data[CONF_HOST]
        self.dhcp_software: str = config_entry.data[CONF_DHCP_SOFTWARE]
        self.ubus = Ubus(
            f"http://{self.host}/ubus",
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
        )
        self._hostapd: list[str] = []
        self._leasefile: str | None = None
        self._mac2name: dict[str, str] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, str | None]:
        """Return the currently connected devices keyed by MAC address."""
        return await self.hass.async_add_executor_job(self._update)

    def _update(self) -> dict[str, str | None]:
        """Query the router, re-authenticating once if the session expired."""
        if self.ubus.session_id is None:
            self._login()
        try:
            return self._read_clients()
        except PermissionError:
            # The router dropped our session (e.g. after a reboot); log back in.
            self._login()
        try:
            return self._read_clients()
        except PermissionError as err:
            raise UpdateFailed(f"Access denied by ubus at {self.host}") from err

    def _login(self) -> None:
        """Open a ubus session, raising UpdateFailed on failure."""
        try:
            session_id = self.ubus.connect()
        except (ConnectionError, PermissionError, TypeError) as err:
            # openwrt-ubus-rpc raises TypeError when the HTTP request itself
            # fails, because it subscripts a None response.
            raise UpdateFailed(f"Error connecting to ubus at {self.host}") from err
        if session_id is None:
            raise UpdateFailed(f"Invalid credentials for ubus at {self.host}")

    def _read_clients(self) -> dict[str, str | None]:
        """Return authorized clients mapped to their DHCP hostname.

        PermissionError is left to propagate so the caller can re-authenticate.
        """
        clients = self._fetch_hostapd_clients()
        if self._mac2name is None:
            self._mac2name = self._generate_mac2name()
        return {
            mac: self._name_for(mac)
            for mac, client in clients.items()
            if client["authorized"]
        }

    def _fetch_hostapd_clients(self) -> dict[str, dict]:
        """Return the raw hostapd client table merged across all interfaces."""
        try:
            if not self._hostapd:
                if not (hostapd := self.ubus.get_hostapd()):
                    raise UpdateFailed(f"No hostapd data from ubus at {self.host}")
                self._hostapd = list(hostapd)
            clients: dict[str, dict] = {}
            for interface in self._hostapd:
                if result := self.ubus.get_hostapd_clients(interface):
                    clients.update(result["clients"])
        except ConnectionError as err:
            raise UpdateFailed(f"Error querying ubus at {self.host}") from err
        return clients

    def _name_for(self, mac: str) -> str | None:
        """Return the DHCP hostname for a MAC address, if known."""
        if self._mac2name is None:
            return None
        return self._mac2name.get(mac.upper())

    def _generate_mac2name(self) -> dict[str, str] | None:
        """Build the MAC-to-hostname map for the configured DHCP software."""
        if self.dhcp_software == "dnsmasq":
            return self._dnsmasq_mac2name()
        if self.dhcp_software == "odhcpd":
            return self._odhcpd_mac2name()
        return {}

    def _dnsmasq_mac2name(self) -> dict[str, str] | None:
        """Read the dnsmasq lease file. Returns None to retry if unavailable."""
        try:
            if self._leasefile is None:
                if not (result := self.ubus.get_uci_config("dhcp", "dnsmasq")):
                    return None
                self._leasefile = next(iter(result["values"].values()))["leasefile"]
            result = self.ubus.file_read(self._leasefile)
        except ConnectionError as err:
            raise UpdateFailed(
                f"Error reading leases from ubus at {self.host}"
            ) from err

        if not result:
            return None

        mac2name = {}
        for line in result["data"].splitlines():
            hosts = line.split(" ")
            mac2name[hosts[1].upper()] = hosts[3]
        return mac2name

    def _odhcpd_mac2name(self) -> dict[str, str] | None:
        """Read the odhcpd leases. Returns None to retry if unavailable."""
        try:
            result = self.ubus.get_dhcp_method("ipv4leases")
        except ConnectionError as err:
            raise UpdateFailed(
                f"Error reading leases from ubus at {self.host}"
            ) from err

        if not result:
            return None

        mac2name = {}
        for device in result["device"].values():
            for lease in device["leases"]:
                mac = ":".join(
                    lease["mac"][i : i + 2] for i in range(0, len(lease["mac"]), 2)
                )
                mac2name[mac.upper()] = lease["hostname"]
        return mac2name
