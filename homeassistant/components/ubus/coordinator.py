"""DataUpdateCoordinator for the OpenWrt (ubus) integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime, timedelta
import logging
from typing import NamedTuple, override

from openwrt.ubus import Ubus

from homeassistant.components.device_tracker.const import DEFAULT_CONSIDER_HOME
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SIGNAL_CLIENTS_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)
LEASE_REREAD_INTERVAL = timedelta(minutes=10)

type UbusConfigEntry = ConfigEntry[UbusDataUpdateCoordinator]


class ClientStamp(NamedTuple):
    """The most recent sighting of a client by one config entry."""

    last_seen: datetime
    hostname: str | None
    seq: int


class UbusSharedState:
    """State shared between the ubus config entries.

    ``presence`` maps a normalized (lowercase) MAC address to the most
    recent stamp of each config entry which has seen the client; ``owners``
    maps a MAC address to the config entry that owns its device tracker
    entity; and ``health`` maps a config entry id to the success of its
    last update.

    A client is home while its most recent stamp from a healthy entry is
    within ``DEFAULT_CONSIDER_HOME``. It is unavailable while every entry
    is unhealthy.
    """

    presence: dict[str, dict[str, ClientStamp]]
    owners: dict[str, str]
    health: dict[str, bool]
    seq: int
    _last_signature: tuple | None

    def __init__(self) -> None:
        """Initialize the shared state."""
        self.presence = {}
        self.owners = {}
        self.health = {}
        self.seq = 0
        self._last_signature = None

    @callback
    def stamp(self, entry_id: str, clients: dict[str, str | None]) -> None:
        """Record the clients this entry sees right now."""
        now = dt_util.utcnow()
        for mac, hostname in clients.items():
            self.seq += 1
            self.presence.setdefault(mac.lower(), {})[entry_id] = ClientStamp(
                now, hostname, self.seq
            )

    def latest_stamp(self, mac: str) -> tuple[str, ClientStamp] | None:
        """Return the reporting entry id and most recent stamp of a client.

        Only stamps from healthy entries count, so a client is present
        while its most recent healthy stamp is within
        ``DEFAULT_CONSIDER_HOME``.
        """
        stamps = self.presence.get(mac.lower())
        if not stamps:
            return None
        entry_id = max(
            (entry for entry in stamps if self.health.get(entry, True)),
            key=lambda entry: stamps[entry].seq,
            default=None,
        )
        if entry_id is None:
            return None
        stamp = stamps[entry_id]
        if dt_util.utcnow() - stamp.last_seen > DEFAULT_CONSIDER_HOME:
            return None
        return entry_id, stamp

    @callback
    def remove_entry(self, entry_id: str) -> None:
        """Drop the stamps, claims and health of a config entry."""
        for stamps in list(self.presence.items()):
            if entry_id in stamps[1]:
                del stamps[1][entry_id]
                if not stamps[1]:
                    del self.presence[stamps[0]]
        self.owners = {
            mac: owner for mac, owner in self.owners.items() if owner != entry_id
        }
        self.health.pop(entry_id, None)

    @callback
    def async_notify(self, hass: HomeAssistant) -> None:
        """Signal the trackers when the presence or health changed."""
        signature = self._signature()
        if signature != self._last_signature:
            self._last_signature = signature
            async_dispatcher_send(hass, SIGNAL_CLIENTS_UPDATED)

    def _signature(self) -> tuple:
        """Return a signature of the current presence and health."""
        home: list[tuple[str, str | None, str | None, bool]] = []
        for mac in self.presence:
            if (latest := self.latest_stamp(mac)) is None:
                home.append((mac, None, None, False))
            else:
                entry_id, stamp = latest
                home.append((mac, entry_id, stamp.hostname, True))
        return (tuple(sorted(home)), tuple(sorted(self.health.items())))


class UbusDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str | None]]):
    """Fetch the authorized wireless clients from an OpenWrt router over ubus."""

    config_entry: UbusConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: UbusConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        self.host: str = config_entry.data[CONF_HOST]
        self.dhcp_software: str = config_entry.data[CONF_DHCP_SOFTWARE]
        scheme = "https" if config_entry.data.get(CONF_SSL, DEFAULT_SSL) else "http"
        self.ubus = Ubus(
            f"{scheme}://{self.host}/ubus",
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            verify=config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        self._hostapd: list[str] = []
        self._leasefile: str | None = None
        self._mac2name: dict[str, str] | None = None
        self._unnamed: set[str] = set()
        self._last_lease_read = datetime.min.replace(tzinfo=dt_util.UTC)
        self._unloaded = False

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
        clients = await self.hass.async_add_executor_job(self._update)
        # A refresh may finish after the entry was unloaded; stamping its
        # results would resurrect the clients released during the unload.
        if not self._unloaded:
            shared: UbusSharedState = self.hass.data[DOMAIN]
            shared.stamp(self.config_entry.entry_id, clients)
        return clients

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Record this router's health and signal the changed trackers."""
        if self._unloaded:
            return
        shared: UbusSharedState = self.hass.data[DOMAIN]
        shared.health[self.config_entry.entry_id] = self.last_update_success
        shared.async_notify(self.hass)

    @callback
    def async_unload(self) -> None:
        """Drop this router's stamps and signal the remaining trackers."""
        self._unloaded = True
        shared: UbusSharedState = self.hass.data[DOMAIN]
        shared.remove_entry(self.config_entry.entry_id)
        shared.async_notify(self.hass)

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
        authorized = [mac for mac, client in clients.items() if client["authorized"]]
        known = self._mac2name or {}
        unnamed = {mac.upper() for mac in authorized} - known.keys()
        now = dt_util.utcnow()
        # Reread the leases for a new client without a hostname, and only
        # periodically for clients which never get one (e.g. static IPs).
        if (
            self._mac2name is None
            or unnamed - self._unnamed
            or (unnamed and now - self._last_lease_read >= LEASE_REREAD_INTERVAL)
        ):
            self._last_lease_read = now
            if (mac2name := self._generate_mac2name()) is not None:
                # Merge, as an empty or partial read must not forget names.
                self._mac2name = {**known, **mac2name}
                self._unnamed = unnamed - mac2name.keys()
        return {mac: self._name_for(mac) for mac in authorized}

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
            # dnsmasq writes "*" when the client did not send a hostname.
            if hosts[3] != "*":
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
                if hostname := lease["hostname"]:
                    mac2name[mac.upper()] = hostname
        return mac2name
