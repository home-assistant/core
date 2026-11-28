"""DataUpdateCoordinator for the OpenWrt (ubus) integration."""

import asyncio
import contextlib
from datetime import datetime, timedelta
import logging
from typing import Any, NamedTuple, override

from openwrt.ubus import Ubus

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
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
# A router that responds slower than this holds up no tick: its requests time
# out, and the tick period is anchored to the tick start.
REQUEST_TIMEOUT = UPDATE_INTERVAL - timedelta(seconds=2)

type UbusConfigEntry = ConfigEntry["UbusDataUpdateCoordinator"]


def _poll_exception_retrieved(poll: asyncio.Future) -> None:
    """Mark a finished poll's exception as retrieved.

    A poll whose router is removed or reconfigured while it runs is never
    awaited again; without this its failure would be logged as an unhandled
    exception.
    """
    with contextlib.suppress(asyncio.CancelledError):
        poll.exception()


def _settled_poll(host: _UbusHost) -> tuple[datetime, Any]:
    """Fetch one router's client view, stamped with the time it settled.

    The stamp is taken the moment the fetch returns in the worker, so a
    poll which outlives a timed-out tick is stamped when it finished, not
    when a later tick consumes it; each poll is stamped at its own
    completion, so a slow router does not stretch the sighting times of
    the clients the fast routers saw.
    """
    view = host.poll()
    return dt_util.utcnow(), view


async def _poll_observed(
    poll: asyncio.Future[tuple[datetime, Any]],
) -> tuple[datetime, Any]:
    """Await one router's poll, returning its view and settle time."""
    return await asyncio.wait_for(
        asyncio.shield(poll),
        timeout=REQUEST_TIMEOUT.total_seconds(),
    )


class InvalidCredentialsError(UpdateFailed):
    """The router rejected the configured credentials."""


class ClientStamp(NamedTuple):
    """The most recent sighting of a client by one router."""

    last_seen: datetime
    hostname: str | None
    seq: int


# The merged presence: MAC -> subentry id -> stamp.
type ClientPresence = dict[str, dict[str, ClientStamp]]


def subentry_signature(subentry: ConfigSubentry) -> tuple:
    """Return a signature of a router subentry, as the coordinator polls it."""
    return (
        tuple(sorted(subentry.data.items())),
        subentry.title,
        subentry.unique_id,
    )


class _UbusHost:
    """The ubus session and lease state of one router."""

    def __init__(self, subentry: ConfigSubentry) -> None:
        """Initialize the host state from the subentry's router data."""
        data = subentry.data
        self.subentry_id: str = subentry.subentry_id
        self.host: str = data[CONF_HOST]
        self.dhcp_software: str = data[CONF_DHCP_SOFTWARE]
        scheme = "https" if data.get(CONF_SSL, DEFAULT_SSL) else "http"
        self.ubus = Ubus(
            f"{scheme}://{self.host}/ubus",
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            verify=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            timeout=REQUEST_TIMEOUT.total_seconds(),
        )
        self.hostapd: list[str] = []
        self.leasefile: str | None = None
        self.mac2name: dict[str, str] | None = None
        self.unnamed: set[str] = set()
        self.last_lease_read: datetime = datetime.min.replace(tzinfo=dt_util.UTC)
        self.signature = subentry_signature(subentry)

    def poll(self) -> dict[str, str | None]:
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
        except PermissionError as err:
            # The router rejected the configured credentials.
            raise InvalidCredentialsError(
                f"Invalid credentials for ubus at {self.host}"
            ) from err
        except (ConnectionError, TypeError) as err:
            # openwrt-ubus-rpc raises TypeError when the HTTP request itself
            # fails, because it subscripts a None response.
            raise UpdateFailed(f"Error connecting to ubus at {self.host}") from err
        if session_id is None:
            raise InvalidCredentialsError(
                f"Invalid credentials for ubus at {self.host}"
            )

    def _read_clients(self) -> dict[str, str | None]:
        """Return authorized clients mapped to their DHCP hostname.

        MAC addresses are lowercase, the one form every consumer keys on.
        PermissionError is left to propagate so the caller can re-authenticate.
        """
        clients = self._fetch_hostapd_clients()
        # Filter list of client MAC addresses by authorization status, then
        # make sure they are unique to preserve the invariant that callers
        # expect unique MACs.  Sort the set so it is stable.
        authorized = sorted(
            {client["mac"] for client in clients if client["authorized"]}
        )
        known = self.mac2name or {}
        unnamed = {mac.upper() for mac in authorized} - known.keys()
        now = dt_util.utcnow()
        # Reread the leases for a new client without a hostname, and only
        # periodically for clients which never get one (e.g. static IPs).
        if (
            self.mac2name is None
            or unnamed - self.unnamed
            or (unnamed and now - self.last_lease_read >= LEASE_REREAD_INTERVAL)
        ):
            self.last_lease_read = now
            if (mac2name := self._generate_mac2name()) is not None:
                # Merge, as an empty or partial read must not forget names.
                self.mac2name = {**known, **mac2name}
                self.unnamed = unnamed - mac2name.keys()
        return {mac.lower(): self._name_for(mac) for mac in authorized}

    def _fetch_hostapd_clients(self) -> list[dict]:
        """Return the raw hostapd client table from all interfaces."""
        try:
            if not self.hostapd:
                if not (hostapd := self.ubus.get_hostapd()):
                    raise UpdateFailed(f"No hostapd data from ubus at {self.host}")
                self.hostapd = list(hostapd)
            clients: list[dict] = []
            for interface in self.hostapd:
                if result := self.ubus.get_hostapd_clients(interface):
                    # Keep per-interface records, even when a client appears
                    # to be "duplicate", as authorization can differ between
                    # interfaces for the same client due to band steering or
                    # other forms of roaming.
                    for mac, client_data in result["clients"].items():
                        clients.append({**client_data, "mac": mac})
        except ConnectionError as err:
            raise UpdateFailed(f"Error querying ubus at {self.host}") from err
        return clients

    def _name_for(self, mac: str) -> str | None:
        """Return the DHCP hostname for a MAC address, if known."""
        if self.mac2name is None:
            return None
        return self.mac2name.get(mac.upper())

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
            if self.leasefile is None:
                if not (result := self.ubus.get_uci_config("dhcp", "dnsmasq")):
                    return None
                self.leasefile = next(iter(result["values"].values()))["leasefile"]
            result = self.ubus.file_read(self.leasefile)
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


class UbusDataUpdateCoordinator(DataUpdateCoordinator[ClientPresence]):
    """Fetch the authorized wireless clients of every router over ubus.

    Every tick polls all routers in parallel, each with its own ubus session
    and lease state. The per-tick results are merged into one presence map,
    so a client roaming between routers, or between the bands of one router,
    keeps one fresh stamp.
    """

    config_entry: UbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UbusConfigEntry,
    ) -> None:
        """Initialize the coordinator on the hub entry.

        The entry-level "disable polling" preference acts on every router,
        as they are all polled by this one coordinator.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        # The routers polled on the last tick, keyed by subentry id.
        self.hosts: dict[str, _UbusHost] = {}
        # The success of each router's last poll; a router never polled is
        # healthy by default.
        self.host_health: dict[str, bool] = {}
        # The client view of each router as of its last successful poll; a
        # router which failed its last poll sees nothing.
        self.latest_views: dict[str, dict[str, str | None]] = {}
        # The subentries as the routers were last polled; an update listener
        # compares this to detect a change, as subentry updates mutate the
        # subentries in place. None until the first poll built the hosts.
        self._polled_signature: tuple | None = None
        # The host each subentry's stamps were last recorded under; the
        # subentry id survives a host change, so a stamp is only valid
        # while the subentry still polls the same host.
        self._stamp_hosts: dict[str, str] = {}
        self._tick_results: dict[str, BaseException | dict[str, str | None]] = {}
        # The poll running in the executor for each router; a tick which
        # times out re-awaits the same poll on the next tick, so two polls
        # never mutate a router's session and lease state at once.
        self._inflight: dict[_UbusHost, asyncio.Future[tuple[datetime, Any]]] = {}
        self._tick_start: float | None = None
        self._last_signature: tuple | None = None
        self._seq = 0
        # Clients whose only stamps were released with a removed router; a
        # client's absence cannot be verified while its last known router
        # is unmonitored, so the set lives until the client is seen again.
        self._ungrounded: set[str] = set()

    def _subentries_signature(self) -> tuple:
        """Return a signature of the entry's subentries, as polled."""
        return tuple(
            (
                subentry_id,
                subentry_signature(subentry),
            )
            for subentry_id, subentry in sorted(self.config_entry.subentries.items())
        )

    def subentries_changed(self) -> bool:
        """Return whether the entry's subentries changed since the last poll."""
        return self._subentries_signature() != self._polled_signature

    def _prune_stamps(self, presence: ClientPresence) -> ClientPresence:
        """Drop the stamps of gone or rehosted routers.

        The rest are kept, as a client stays reported while its newest
        stamp is within consider_home. A reconfigured router's stamps
        stand while the host is unchanged.
        """
        subentries = self.config_entry.subentries
        pruned: ClientPresence = {}
        for mac, per_host in presence.items():
            for subentry_id, stamp in per_host.items():
                subentry = subentries.get(subentry_id)
                if subentry is None or (
                    self._stamp_hosts.get(subentry_id) != subentry.data[CONF_HOST]
                ):
                    continue
                pruned.setdefault(mac, {})[subentry_id] = stamp
        return pruned

    @override
    async def _async_update_data(self) -> ClientPresence:
        """Poll every router in parallel and merge their client views.

        Each view is merged and published as soon as it settles, so a
        router that hangs does not delay the healthy routers' sightings
        by the full request timeout.
        """
        hosts = self._reconcile_hosts()
        if not hosts:
            # No routers configured yet; nothing to fetch.
            # The clients lose every stamp here, and their absence cannot
            # be verified while their last known router is unmonitored.
            self._ungrounded |= set(self.data_or_none or {})
            return {}
        polls: list[asyncio.Future[tuple[datetime, Any]]] = []
        for host in hosts.values():
            poll = self._inflight.get(host)
            if poll is None:
                poll = self.hass.async_add_executor_job(_settled_poll, host)
                poll.add_done_callback(_poll_exception_retrieved)
                self._inflight[host] = poll
            polls.append(poll)
        old: ClientPresence = self.data_or_none or {}
        presence = self._prune_stamps(old)
        self._tick_results = {}
        observed_at: dict[str, datetime] = {}
        pending: dict[asyncio.Task[tuple[datetime, Any]], _UbusHost] = {
            asyncio.create_task(_poll_observed(poll)): host
            for host, poll in zip(hosts.values(), polls, strict=True)
        }
        try:
            while pending:
                done, _ = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                settled: list[
                    tuple[_UbusHost, BaseException | tuple[datetime, Any]]
                ] = []
                for task in done:
                    host = pending.pop(task)
                    # A poll which finished while observed is no longer in
                    # flight, so the next tick starts a fresh poll for the
                    # router; one which timed out keeps running and is
                    # re-awaited by the next tick.
                    if (poll := self._inflight.get(host)) is not None and poll.done():
                        self._inflight.pop(host, None)
                    # The subentry id survives a host change, so a removed
                    # or reconfigured router's in-flight result must not
                    # feed the merge.
                    subentry = self.config_entry.subentries.get(host.subentry_id)
                    if subentry is None or host.signature != subentry_signature(
                        subentry
                    ):
                        # The stale result is never awaited again, so
                        # retrieve its exception; the callback on the
                        # executor future does not reach this task.
                        _poll_exception_retrieved(task)
                        self.latest_views.pop(host.subentry_id, None)
                        continue
                    # The observed task is done, so its outcome is
                    # retrievable without blocking; a cancelled task
                    # counts as a failure.
                    if task.cancelled():
                        settled.append((host, asyncio.CancelledError()))
                        continue
                    if (exc := task.exception()) is None:
                        settled.append((host, task.result()))
                    else:
                        settled.append((host, exc))
                fresh: list[tuple[str, dict[str, str | None]]] = []
                for host, result in settled:
                    subentry_id = host.subentry_id
                    if isinstance(result, BaseException):
                        # A failed poll sees nothing new.
                        self.latest_views.pop(subentry_id, None)
                        self._tick_results[subentry_id] = result
                        continue
                    self.latest_views[subentry_id] = result[1]
                    observed_at[subentry_id] = result[0]
                    fresh.append((subentry_id, result[1]))
                    self._tick_results[subentry_id] = result[1]
                # Stamps are sequenced by observation time, so the newest
                # sighting reports the client's source.
                subentries = self.config_entry.subentries
                for subentry_id, view in sorted(
                    fresh, key=lambda item: observed_at[item[0]]
                ):
                    # Record the host the stamp now stands under, so stamps
                    # recorded for a different host are dropped on the
                    # next merge.
                    self._stamp_hosts[subentry_id] = subentries[subentry_id].data[
                        CONF_HOST
                    ]
                    for mac, hostname in view.items():
                        self._seq += 1
                        presence.setdefault(mac, {})[subentry_id] = ClientStamp(
                            observed_at[subentry_id], hostname, self._seq
                        )
                # A router removed or rehosted mid-tick loses its stamps in
                # the same tick the tick-end merge would have dropped them.
                presence = self._prune_stamps(presence)
                # A client which loses every stamp in the merge was last seen
                # on a router which is no longer monitored.
                self._ungrounded = (self._ungrounded | set(old)) - set(presence)
                self.data = presence
                self.async_signal_clients_updated()
        finally:
            for task in pending:
                task.cancel()
        failed = {
            subentry_id
            for subentry_id, result in self._tick_results.items()
            if isinstance(result, BaseException)
        }
        if failed and len(failed) == len(self._tick_results):
            # Every router failed; the pruned presence published above
            # stands in for the old data, as stamps of gone routers would
            # count as healthy.
            errors = [
                result
                for result in self._tick_results.values()
                if isinstance(result, BaseException)
            ]
            if len(errors) == 1:
                # A single router: report its own failure.
                raise errors[0]
            raise UpdateFailed(
                "All routers failed to respond: "
                + ", ".join(self.hosts[subentry_id].host for subentry_id in failed)
            )
        return presence

    def _reconcile_hosts(self) -> dict[str, _UbusHost]:
        """Align the polled routers with the entry's subentries."""
        if not self.subentries_changed():
            return self.hosts
        subentries = self.config_entry.subentries
        # Drop the state of routers that are gone, releasing their
        # credential issues.
        for subentry_id in (
            set(self.hosts) | set(self.host_health) | set(self.latest_views)
        ):
            if subentry_id not in subentries:
                host = self.hosts.pop(subentry_id, None)
                if host is not None:
                    self._inflight.pop(host, None)
                self.host_health.pop(subentry_id, None)
                self.latest_views.pop(subentry_id, None)
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"invalid_credentials_{subentry_id}"
                )
        # Rebuild routers whose data changed, so their session and lease
        # state start clean with the new configuration.
        for subentry_id, subentry in subentries.items():
            host = self.hosts.get(subentry_id)
            if host is None or subentry_signature(subentry) != host.signature:
                if host is not None:
                    # A reconfigured router's stuck poll queries the old
                    # configuration; it must not feed the new one, and its
                    # client view is for the old host.
                    self._inflight.pop(host, None)
                    self.latest_views.pop(subentry_id, None)
                    # The health record belongs to the old host.
                    self.host_health.pop(subentry_id, None)
                    self._async_delete_credentials_issue(subentry_id)
                self.hosts[subentry_id] = _UbusHost(subentry)
        self._polled_signature = self._subentries_signature()
        return self.hosts

    @override
    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Anchor the next tick to this tick's start.

        The base schedules the next refresh after the refresh completes,
        which would stretch the tick period with slow or timed-out routers.
        """
        self._tick_start = self.hass.loop.time()
        try:
            await super()._async_refresh(
                log_failures=log_failures,
                raise_on_auth_failed=raise_on_auth_failed,
                scheduled=scheduled,
                raise_on_entry_error=raise_on_entry_error,
            )
        finally:
            self._tick_start = None

    @callback
    @override
    def _schedule_refresh(self) -> None:
        """Schedule the next tick, phase-locked to the current tick's start."""
        if self._update_interval_seconds is None:
            return
        interval = self._update_interval_seconds
        if self._tick_start is not None:
            # Anchor the next tick to this tick's start, so a slow tick does
            # not stretch the period; an overrun tick fires right away.
            self._update_interval_seconds = max(
                interval - (self.hass.loop.time() - self._tick_start), 0
            )
        try:
            super()._schedule_refresh()
        finally:
            self._update_interval_seconds = interval

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Record host health, manage credential issues, signal changes."""
        for subentry_id, result in self._tick_results.items():
            was_healthy = self.host_health.get(subentry_id, True)
            if isinstance(result, BaseException):
                self.host_health[subentry_id] = False
                if isinstance(result, InvalidCredentialsError):
                    self._async_create_credentials_issue(subentry_id)
                if was_healthy:
                    # With another router carrying the tick, this failure
                    # would otherwise be discarded unlogged.
                    _LOGGER.warning(
                        "Router %s is unreachable: %s",
                        self._router_host(subentry_id),
                        result,
                    )
            else:
                self.host_health[subentry_id] = True
                self._async_delete_credentials_issue(subentry_id)
                if not was_healthy:
                    _LOGGER.info(
                        "Router %s is reachable again",
                        self._router_host(subentry_id),
                    )
        self._tick_results = {}
        subentries = self.config_entry.subentries
        for subentry_id in list(self.host_health):
            if subentry_id not in subentries:
                del self.host_health[subentry_id]
        self.async_signal_clients_updated()

    @callback
    def _async_create_credentials_issue(self, subentry_id: str) -> None:
        """Keep a repair issue open while the credentials keep failing.

        There is no subentry reauth, so persistent invalid credentials are
        surfaced as a repair right away instead of prompting for them.
        """
        if (host := self.hosts.get(subentry_id)) is None:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"invalid_credentials_{subentry_id}",
            config_entry_id=self.config_entry.entry_id,
            config_subentry_id=subentry_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="persistent_invalid_credentials",
            translation_placeholders={"host": host.host},
        )

    @callback
    def _async_delete_credentials_issue(self, subentry_id: str) -> None:
        """Close the credential repair when the router answers again."""
        ir.async_delete_issue(self.hass, DOMAIN, f"invalid_credentials_{subentry_id}")

    def _router_host(self, subentry_id: str) -> str:
        """Return the host of a subentry's router, for log messages."""
        if (host := self.hosts.get(subentry_id)) is not None:
            return host.host
        return subentry_id

    @callback
    def async_signal_clients_updated(self) -> None:
        """Signal the trackers when the presence, health or options changed."""
        signature = self._signature()
        if signature != self._last_signature:
            self._last_signature = signature
            async_dispatcher_send(self.hass, SIGNAL_CLIENTS_UPDATED)

    def _signature(self) -> tuple:
        """Return a signature of the presence, health and router setup."""
        data = self.data_or_none or {}
        home: list[tuple[str, str | None, str | None, int | None, bool]] = []
        for mac in data:
            if (latest := self.latest_stamp(mac)) is None:
                home.append((mac, None, None, None, False))
            else:
                subentry_id, stamp = latest
                # The resolved hostname and the sighting sequence, so a
                # fresh sighting or a hostname learned by another router
                # signals even when the tracker state is unchanged.
                home.append(
                    (
                        mac,
                        subentry_id,
                        stamp.hostname or self.known_hostname(mac),
                        stamp.seq,
                        True,
                    )
                )
        return (
            tuple(sorted(home)),
            tuple(sorted(self.host_health.items())),
            self._subentries_signature(),
            self._consider_home(),
        )

    def _consider_home(self) -> timedelta:
        """Return the configured keep-home window, defaulting to the standard one."""
        seconds = self.config_entry.options.get(CONF_CONSIDER_HOME)
        if seconds is None:
            return DEFAULT_CONSIDER_HOME
        return timedelta(seconds=seconds)

    def latest_stamp(self, mac: str) -> tuple[str, ClientStamp] | None:
        """Return the reporting subentry id and most recent healthy stamp.

        Only stamps from healthy routers count, so a client is present while
        its most recent healthy stamp is within consider_home.
        """
        data = self.data_or_none
        if not data:
            return None
        stamps = data.get(mac.lower())
        if not stamps:
            return None
        subentry_id = max(
            (sid for sid in stamps if self.host_health.get(sid, True)),
            key=lambda sid: stamps[sid].seq,
            default=None,
        )
        if subentry_id is None:
            return None
        stamp = stamps[subentry_id]
        if dt_util.utcnow() - stamp.last_seen > self._consider_home():
            return None
        return subentry_id, stamp

    def has_reportable_stamp(self, mac: str) -> bool:
        """Return whether the client's state is grounded on a reachable router.

        The client is reported while its freshest stamp is from a healthy
        router, or while a healthy router has seen it within consider_home.
        A fresher stamp on a router which no longer updates is unverifiable,
        so once no healthy router has seen the client recently, it is
        unavailable rather than not home.
        """
        data = self.data_or_none
        if not data:
            return False
        stamps = data.get(mac.lower())
        if not stamps:
            return False
        latest = max(stamps, key=lambda sid: stamps[sid].seq)
        return self.host_health.get(latest, True) or self.latest_stamp(mac) is not None

    def known_away(self, mac: str) -> bool:
        """Return whether the client's absence is established by the routers.

        A client no router reports is known to be away only when every
        configured router answers and it was not last seen on a router
        which is no longer monitored.
        """
        return (
            bool(self.hosts)
            and mac.lower() not in self._ungrounded
            and all(
                self.host_health.get(subentry_id, True) for subentry_id in self.hosts
            )
        )

    def known_hostname(self, mac: str) -> str | None:
        """Return the most recent non-empty hostname stamped for a client."""
        data = self.data_or_none
        if not data:
            return None
        stamps = [
            stamp for stamp in data.get(mac.lower(), {}).values() if stamp.hostname
        ]
        if not stamps:
            return None
        return max(stamps, key=lambda stamp: stamp.seq).hostname
