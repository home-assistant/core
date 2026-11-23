"""DataUpdateCoordinator for the OpenWrt (ubus) integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime, timedelta
import logging
from typing import NamedTuple, override

from openwrt.ubus import Ubus

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
# A client dropped by its last reporting router is kept visible until every
# router has polled again, or one further poll cycle has passed, so a roam is
# not announced as a departure before the new router has polled.
DEPARTURE_GRACE = UPDATE_INTERVAL
LEASE_REREAD_INTERVAL = timedelta(minutes=10)

type UbusConfigEntry = ConfigEntry[UbusDataUpdateCoordinator]


class RouterReport(NamedTuple):
    """The latest report of a client by one router."""

    hostname: str | None
    seq: int


class UbusSharedState:
    """State shared between the ubus config entries.

    ``reports`` maps a MAC address to the latest report of each router
    which still sees the client; ``owners`` maps a MAC address to the
    config entry that owns its device tracker entity; ``health`` maps a
    router host to the success of its last update; ``departing`` maps a
    MAC address to the moment its last router stopped seeing it; and
    ``last_poll`` maps a router host to the time of its last successful
    poll.
    """

    reports: dict[str, dict[str, RouterReport]]
    owners: dict[str, str]
    health: dict[str, bool]
    departing: dict[str, tuple[datetime, str, RouterReport]]
    last_poll: dict[str, datetime]
    seq: int

    def __init__(self) -> None:
        """Initialize the shared state."""
        self.reports = {}
        self.owners = {}
        self.health = {}
        self.departing = {}
        self.last_poll = {}
        self.seq = 0

    def latest_report(self, mac: str) -> tuple[str, RouterReport] | None:
        """Return the reporting host and latest report of a visible client.

        A client which its last router has dropped stays visible, sourced
        from its last reporter, until every router has polled again or one
        further poll cycle has passed, so a roam is not announced as a
        departure before the new router has polled.
        """
        seen_by = self.reports.get(mac)
        if seen_by:
            source = max(seen_by, key=lambda host: seen_by[host].seq)
            return source, seen_by[source]
        if (departed := self.departing.get(mac)) is None:
            return None
        since, source, report = departed
        if dt_util.utcnow() >= since + DEPARTURE_GRACE or not any(
            last < since for last in self.last_poll.values()
        ):
            return None
        return source, report


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
        # A refresh may finish after the entry was unloaded; publishing its
        # results would restore the clients released during the unload.
        if not self._unloaded:
            shared: UbusSharedState = self.hass.data[DOMAIN]
            shared.last_poll[self.host] = dt_util.utcnow()
            self._async_publish_clients(clients)
        return clients

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Release claimed clients and record this router's health."""
        if self._unloaded:
            return
        shared: UbusSharedState = self.hass.data[DOMAIN]
        healthy = self.last_update_success
        health_changed = shared.health.get(self.host, True) != healthy
        shared.health[self.host] = healthy
        if not healthy:
            self.clear_clients()
        if health_changed:
            async_dispatcher_send(self.hass, SIGNAL_CLIENTS_UPDATED)

    @callback
    def _async_publish_clients(self, clients: dict[str, str | None]) -> bool:
        """Publish which clients this router sees to the shared state.

        Each router keeps its own report for the clients it sees, so a
        client stays reported while any router still sees it, and the
        source follows the router which reported it most recently.

        Returns whether a client's visibility changed.
        """
        shared: UbusSharedState = self.hass.data[DOMAIN]
        reports = shared.reports

        def visible_tuple(mac: str) -> tuple[str, RouterReport] | None:
            """Return the client's reporting source, ignoring the handover window."""
            seen_by = reports.get(mac)
            if seen_by:
                source = max(seen_by, key=lambda host: seen_by[host].seq)
                return source, seen_by[source]
            if (departed := shared.departing.get(mac)) is None:
                return None
            return departed[1], departed[2]

        affected = set(clients)
        affected.update(mac for mac, seen_by in reports.items() if self.host in seen_by)
        affected.update(shared.departing)
        before = {mac: visible_tuple(mac) for mac in affected}

        now = dt_util.utcnow()
        for mac, hostname in clients.items():
            shared.seq += 1
            reports.setdefault(mac, {})[self.host] = RouterReport(hostname, shared.seq)
            shared.departing.pop(mac, None)
        for mac, seen_by in list(reports.items()):
            if self.host in seen_by and mac not in clients:
                report = seen_by.pop(self.host)
                if not seen_by:
                    # The last router stopped seeing the client; keep it
                    # visible until every router has polled again.
                    del reports[mac]
                    shared.departing[mac] = (now, self.host, report)
        for mac, (since, _source, _report) in list(shared.departing.items()):
            if now >= since + DEPARTURE_GRACE or not any(
                last < since for last in shared.last_poll.values()
            ):
                del shared.departing[mac]

        changed = any(visible_tuple(mac) != before[mac] for mac in affected)
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_CLIENTS_UPDATED)
        return changed

    @callback
    def clear_clients(self) -> bool:
        """Release every client claimed by this router.

        Returns whether a client's visibility changed.
        """
        return self._async_publish_clients({})

    @callback
    def async_unload(self) -> None:
        """Release this router's clients and ignore late refresh results.

        A refresh in flight when the entry unloads is ignored, and the
        remaining trackers are signalled even if this router has no reports
        left, so they re-evaluate availability without it.
        """
        self._unloaded = True
        if not self.clear_clients():
            async_dispatcher_send(self.hass, SIGNAL_CLIENTS_UPDATED)

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
