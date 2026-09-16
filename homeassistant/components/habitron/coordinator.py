"""Habitron integration using DataUpdateCoordinator."""

import asyncio
from dataclasses import dataclass
from ipaddress import IPv4Address
import logging
from typing import override
from urllib.parse import quote

from habitron_client import (
    HabitronClient,
    HabitronConnectionError,
    HabitronError,
    HabitronTimeoutError,
    Router,
    SmartHub,
    async_build_hub,
    async_build_system,
    async_refresh_hub,
    async_refresh_system,
    get_host_ip,
    get_own_ip,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration

from .const import CONF_DEFAULT_HOST, DOMAIN, SCAN_INTERVAL

type HabitronConfigEntry = ConfigEntry[HbtnCoordinator]
"""Typed config entry alias. ``entry.runtime_data`` holds the HbtnCoordinator,
which owns the bus client and both halves of the model: the ``SmartHub`` (the
hub's own data and host readings) and the ``Router`` (everything behind it).
"""

_LOGGER = logging.getLogger(__name__)

MANUFACTURER = "Habitron GmbH"

# Bus port of the SmartHub, and the port its standalone web UI answers on.
_BUS_PORT = 7777
_WEB_PORT = 7780

# Timeout for one bus poll. Generous: a poll walks every module on the bus.
_POLL_TIMEOUT = 20


def _is_ipv4(value: str) -> bool:
    """Whether ``value`` is already a literal IPv4 address."""
    try:
        IPv4Address(value)
    except ValueError:
        return False
    return True


def _area_name(router: Router, area_no: int) -> str:
    """Return the bus area name for ``area_no`` (or ``House``)."""
    for area in router.areas:
        if area.nmbr == area_no:
            return area.name
    return "House"


@dataclass(frozen=True, slots=True)
class HbtnData:
    """The coordinator's change-detection key.

    With ``always_update=False`` the fan-out happens only when this differs
    from the previous tick, so anything no member notification carries has to
    be in here -- which is why the host state travels beside the bus CRC.
    """

    crc: int
    host_readings_ok: bool


class HbtnCoordinator(DataUpdateCoordinator[HbtnData]):
    """Habitron data update coordinator.

    Owns the connection and the whole model. ``async_refresh_system`` writes the
    bus status directly into the module/input/output objects and
    ``async_refresh_hub`` does the same for the hub's host readings; the
    entities read those object attributes via their
    ``_handle_coordinator_update`` callbacks. The coordinator acts as a
    heartbeat that fans out update events.

    ``_async_update_data`` returns an :class:`HbtnData`, which serves as the
    change-detection key. With ``always_update=False`` the coordinator only
    fans out to the entities when something they show actually changed between
    ticks, avoiding a needless write of every entity on every tick.
    """

    def __init__(self, hass: HomeAssistant, entry: HabitronConfigEntry) -> None:
        """Initialize Habitron update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Habitron updates",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.entry = entry

        # Built in ``_async_setup``; empty models until then, so nothing has to
        # guard against ``None``.
        self._client: HabitronClient | None = None
        self.hub = SmartHub()
        self.router = Router()

        # Address the hub was reached at -- deliberately not the address the hub
        # reports for itself: hubs answer with ``0.0.0.0`` when their interface
        # is unnumbered from their own point of view, and even a valid answer
        # describes the hub's network, not the one Home Assistant reached it
        # from. This ends up in every device's ``configuration_url``, so it has
        # to be the address that actually works here.
        self.host = ""
        self.base_url = ""

        # Whether ``hub.uid`` is the hub's own identity or the fallback written
        # in below. Recorded before the fallback overwrites it.
        self._uid_from_mac = False

        # Compact-status CRC handed back to the library on each poll so an
        # unchanged bus skips the module re-parse.
        self.crc = 0

        # Whether the last host poll answered. The hub's own readings are
        # refreshed separately and their errors are swallowed (see
        # ``_async_update_host``), so without this they would keep reporting
        # their last value indefinitely, indistinguishable from a live one.
        # ``SmartHub.host_valid`` cannot say this: it means "a host poll has
        # ever succeeded" and never goes back to false.
        self.host_readings_ok = True

        # Integration version reported to the hub. Resolved from the loader in
        # ``_async_setup`` (core manifests carry no version, so it stays 0.0.0
        # there).
        self._hbtn_version = "0.0.0"

    @property
    def client(self) -> HabitronClient:
        """Return the connected client.

        ``_async_setup`` constructs and connects it; calling any wire method
        before then is a programming error.
        """
        if self._client is None:
            raise RuntimeError("HabitronClient is not connected; setup has not run")
        return self._client

    @property
    def smhub_name(self) -> str:
        """Configured name of the SmartHub (the config entry title)."""
        return self.entry.title

    @property
    def uid(self) -> str:
        """The identity every device and entity of this entry is keyed by.

        Kept on the hub model rather than beside it: the entities of the hub
        read their device identifier off that same object, so a second copy here
        could disagree with the one they use.
        """
        return self.hub.uid

    @property
    def has_mac_uid(self) -> bool:
        """Whether :attr:`uid` is the hub's own identity rather than a fallback.

        False until the hub has actually reported a usable address, so nothing
        keys on the placeholder the coordinator starts with.
        """
        return self._uid_from_mac

    @override
    async def _async_setup(self) -> None:
        """Connect and build the model during ``async_config_entry_first_refresh``.

        Runs once before the first ``_async_update_data``: resolves the host,
        opens the client, builds the hub and bus models and registers the
        hub/bus devices.

        Expected connection failures are translated to ``ConfigEntryNotReady``
        here: ``DataUpdateCoordinator`` otherwise logs a raw library error from
        setup as *unexpected* on every retry and replaces it with a generic,
        untranslated ``ConfigEntryNotReady``. ``ConfigEntryError`` (a duplicate
        hub) is deliberately not caught -- that one must not be retried.
        """
        try:
            await self._async_connect_and_build()
        except (TimeoutError, HabitronTimeoutError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connect_timeout",
            ) from err
        except ConnectionRefusedError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connect_refused",
                translation_placeholders={"error": str(err)},
            ) from err
        except (OSError, ConnectionError, HabitronError) as err:
            # The library raises its own HabitronError subclasses (protocol /
            # connection errors) rather than OSError for a flaky or rebooting
            # hub. Treat them as transient so HA retries the entry.
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connect_error",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _async_connect_and_build(self) -> None:
        """Resolve, connect, build both models and register the devices."""
        self.host = await self._async_resolve_host()
        integration = await async_get_integration(self.hass, DOMAIN)
        if integration.version is not None:
            self._hbtn_version = str(integration.version)

        # The client uses a fresh socket per command, so ``connect()`` only
        # opens and closes a probe socket to fail fast on an unreachable host;
        # no connection is kept open afterwards.
        self._client = HabitronClient(self.host, _BUS_PORT)
        await self._client.connect()

        self.hub = await async_build_hub(self._client)
        self._resolve_uid()
        self.base_url = self._resolve_base_url()
        self._register_hub_device()

        # The build needs the hub's event server stopped. The stop is inside the
        # try because a failed stop request may still have reached the hub.
        try:
            await self.client.reinit_hub(0)
            self.router = await async_build_system(self.client, b_uid=self.uid)
            await self._register_bus_devices()
        finally:
            await self.client.reinit_hub(1)

    async def _async_resolve_host(self) -> str:
        """Return the address to reach the hub at.

        Hostname and ``local`` resolution happens here rather than in
        ``__init__`` to keep the blocking DNS lookup off the event loop.
        """
        host: str = self.entry.data[CONF_HOST]
        if _is_ipv4(host):
            return host
        if host == CONF_DEFAULT_HOST:
            # get_own_ip is a plain blocking socket call, so it runs in the
            # executor. get_host_ip resolves the name itself with async DNS, so
            # it must be awaited directly -- handing it to the executor would
            # only build the coroutine and assign that, unrun.
            return await self.hass.async_add_executor_job(get_own_ip)
        return await get_host_ip(host)

    def _resolve_uid(self) -> None:
        """Settle the identity every device and entity of this entry is keyed by.

        The hub derives its own from its LAN address; this adds only what the
        library cannot know -- the fallback for a hub that reports no usable
        address, and the check that no other entry already owns this identity.
        """
        self._uid_from_mac = bool(self.hub.uid)
        if not self._uid_from_mac:
            # Keep whatever the entry is already keyed by. Carrying an empty uid
            # from here would give every device the same blank identifier.
            self.hub.uid = self.entry.unique_id or self.entry.entry_id
            _LOGGER.debug("Hub reported no usable MAC; using %s as uid", self.uid)

        # Before the first registry write: if another entry already owns this
        # hub, its devices and entities are keyed by this very uid, so going on
        # would attach a second, unusable entry to them. Failing here leaves the
        # registry untouched.
        if (
            self._uid_from_mac
            and self.entry.unique_id != self.uid
            and self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, self.uid
            )
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="duplicate_hub",
                translation_placeholders={"host": self.host, "uid": self.uid},
            )

    def _resolve_base_url(self) -> str:
        """Return the base of the hub's own web UI.

        An add-on hub is reached through Home Assistant, a standalone one on
        its own port.

        The slug is the add-on's own panel path: the Supervisor registers one
        per ingress add-on with ``frontend_url_path=addon``
        (``hassio/addon_panel.py``), and ``/ingress`` is the entry within it.
        Not ``homeassistant://app/<slug>``, which several integrations use --
        that is a Companion-app deep link and opens nothing in a browser.
        """
        if self.hub.is_addon:
            return f"homeassistant://{self.hub.slug}/ingress"
        return f"http://{self.host}:{_WEB_PORT}"

    def _conf_url(self, path: str) -> str | None:
        """Return the link to ``path`` in the hub's own web UI.

        An add-on hub is reached through Home Assistant, so the link is stored
        with the ``homeassistant://`` scheme: the frontend rewrites that to a
        plain ``/`` against whatever address the viewer is currently using. One
        stored value then works on the local network and through a remote URL
        alike -- and ``configuration_url`` is stored once, so a resolved
        address could only ever match one of the two. The page inside the app
        travels as the ``index`` query.

        A standalone hub serves its own UI, so that one keeps an absolute URL.
        """
        if not self.host:
            return None
        if self.hub.is_addon:
            # ``safe=""``: the default leaves "/" alone, and the page is a
            # query *value* -- the app's own links carry it encoded.
            return f"{self.base_url}?index={quote(path, safe='')}"
        return f"{self.base_url}{path}"

    def _register_hub_device(self) -> None:
        """Register the SmartHub itself as a device."""
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            configuration_url=self._conf_url("/hub"),
            # Every interface, not just the identifying one: the hub answers
            # over whichever is up, so a discovery that saw the other one must
            # still match this device. The library already dropped anything that
            # is not an address, so the list registers as-is.
            connections={(dr.CONNECTION_NETWORK_MAC, mac) for mac in self.hub.macs},
            identifiers={(DOMAIN, self.uid)},
            manufacturer=MANUFACTURER,
            suggested_area="House",
            name=self.smhub_name,
            # ``platform`` is the hardware ("Raspberry Pi 5"), i.e. the model.
            # The entry title is user-renameable, so it is not stable model
            # metadata; there is no separate hardware revision to report as
            # ``hw_version``.
            model=self.hub.platform,
            sw_version=self.hub.version,
        )

    async def _register_bus_devices(self) -> None:
        """Register the router + module devices and push their registry ids."""
        dev_reg = dr.async_get(self.hass)
        router = self.router

        # ``via_device`` is deprecated (removal in 2027.8), so link through the
        # registry id of the hub device registered above. Looked up scoped to
        # our entry: identifiers are unique only within a config entry.
        hub_dev = dev_reg.async_get_device_by_identifier(
            (DOMAIN, self.uid), self.entry.entry_id
        )
        rt_dev = dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            configuration_url=self._conf_url("/router"),
            identifiers={(DOMAIN, router.uid)},
            manufacturer=MANUFACTURER,
            name=router.name,
            model="Smart Router",
            sw_version=router.version,
            serial_number=router.serial,
            via_device_id=hub_dev.id if hub_dev else None,
        )
        await self.client.send_devregid(0, rt_dev.id)

        for module in router.modules:
            # ``suggested_area`` seeds the area only on device creation; a
            # forced ``async_update_device(area_id=...)`` here would clobber the
            # user's manually chosen area on every reload, so it is
            # intentionally not done.
            dev = dev_reg.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                configuration_url=self._conf_url(f"/module-{module.addr}"),
                identifiers={(DOMAIN, module.uid)},
                manufacturer=MANUFACTURER,
                suggested_area=_area_name(router, module.area),
                name=module.name,
                model=module.mod_type,
                sw_version=module.sw_version,
                hw_version=module.hw_version,
                via_device_id=rt_dev.id,
            )
            await self.client.send_devregid(module.addr, dev.id)

    @override
    async def _async_update_data(self) -> HbtnData:
        """Fetch the current Habitron status.

        Returns the change-detection key (see :class:`HbtnData`);
        ``async_refresh_system`` also updates the model in place and fires the
        per-member listeners. Connection-level failures (timeouts, network
        errors, refused connections) are converted to ``UpdateFailed`` so the
        coordinator flips ``last_update_success`` to False and every
        ``CoordinatorEntity`` is automatically marked unavailable.
        """
        try:
            async with asyncio.timeout(_POLL_TIMEOUT):
                self.crc = await async_refresh_system(
                    self.client, self.router, last_crc=self.crc
                )
        except (TimeoutError, HabitronTimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_timeout",
            ) from err
        except (OSError, ConnectionError, HabitronConnectionError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_network_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except HabitronError as err:
            # Everything else the library raises is about the answer, not the
            # connection: a bad marker, an inconsistent frame length, a CRC
            # that does not match, a module list the bus status contradicts.
            # Reporting those as a network fault sends the user looking in the
            # wrong place.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_protocol_error",
                translation_placeholders={"error": str(err)},
            ) from err
        # Outside the try: the host readings swallow their own errors, so a
        # hub-diag hiccup must not mark every entity unavailable.
        await self._async_update_host()
        self._update_router_issue()
        return HbtnData(crc=self.crc, host_readings_ok=self.host_readings_ok)

    async def _async_update_host(self) -> None:
        """Refresh the hub's own host readings.

        These are non-essential (CPU/memory/disk/log levels) and decoupled from
        the bus status: a transient bad or dropped response must not fail the
        coordinator tick, which would mark *every* entity unavailable. Swallow
        the library's protocol/connection errors and keep the last values; the
        next tick refreshes them. Genuine connectivity loss still surfaces
        through the bus refresh above.

        The failure is recorded in ``host_readings_ok`` so the hub's own
        entities can report themselves unavailable: keeping the last values is
        only defensible while something says they are no longer live.

        A hub platform that reports no host readings is skipped inside
        ``async_refresh_hub`` without a wire round trip.
        """
        try:
            await async_refresh_hub(
                self.client, self.hub, hbtn_version=self._hbtn_version
            )
        except (HabitronError, OSError, TimeoutError) as err:
            _LOGGER.debug("SmartHub host readings skipped: %s", err)
            self.host_readings_ok = False
        else:
            self.host_readings_ok = True

    def async_clear_router_issue(self) -> None:
        """Delete this entry's router repair issue on unload.

        Without this, an entry removed while ``sys_ok`` is false would leave a
        stale repair warning: no later coordinator tick can clear it.
        """
        ir.async_delete_issue(
            self.hass, DOMAIN, f"router_system_error_{self.router.uid}"
        )

    def _update_router_issue(self) -> None:
        """Mirror the router's system-error flag into the issue registry.

        Raised at ``ERROR`` severity and not fixable from Home Assistant: the
        fault is on the bus, so there is nothing a repair flow could do here.
        It clears itself once the router reports a healthy state again.
        """
        issue_id = f"router_system_error_{self.router.uid}"
        if self.router.sys_ok:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="router_system_error",
                translation_placeholders={"name": self.smhub_name},
            )

    async def async_close(self) -> None:
        """Release the bus client on entry unload.

        With per-command sockets there is no long-lived connection to tear down;
        this drops the client reference and lets it close any probe socket it
        may still hold.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None
