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
    normalise_mac,
)

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration

from .const import CONF_DEFAULT_HOST, DOMAIN, SCAN_INTERVAL

type HabitronConfigEntry = ConfigEntry[HbtnCoordinator]

_LOGGER = logging.getLogger(__name__)

MANUFACTURER = "Habitron GmbH"

_BUS_PORT = 7777
_WEB_PORT = 7780

_POLL_TIMEOUT = 20


@callback
def async_hub_macs(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """Return the hub MACs of ``entry``: its unique id and its devices' MACs."""
    macs = {mac} if (mac := normalise_mac(entry.unique_id or "")) else set()
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        macs.update(
            mac
            for kind, value in device.connections
            if kind == dr.CONNECTION_NETWORK_MAC
            and (mac := normalise_mac(value)) is not None
        )
    return macs


def _is_ipv4(value: str) -> bool:
    """Return if ``value`` is a literal IPv4 address."""
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
    """Coordinator data; entities are only updated when it changes."""

    crc: int
    host_readings_ok: bool
    sys_ok: bool


class HbtnCoordinator(DataUpdateCoordinator[HbtnData]):
    """Habitron data update coordinator."""

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

        self._client: HabitronClient | None = None
        self.hub = SmartHub()
        self.router = Router()

        # Address we reached the hub at; its self-reported one can be 0.0.0.0.
        self.host = ""
        self.base_url = ""

        self._uid_from_mac = False

        self.crc = 0

        # Whether the last host poll answered; ``SmartHub.host_valid`` never resets.
        self.host_readings_ok = True

        self._hbtn_version = "0.0.0"

    @property
    def client(self) -> HabitronClient:
        """Return the connected client."""
        if self._client is None:
            raise RuntimeError("HabitronClient is not connected; setup has not run")
        return self._client

    @property
    def smhub_name(self) -> str:
        """Return the configured name of the SmartHub."""
        return self.entry.title

    @property
    def uid(self) -> str:
        """Return the hub uid all devices of this entry are keyed by."""
        return self.hub.uid

    @property
    def has_mac_uid(self) -> bool:
        """Return if :attr:`uid` is the hub's MAC rather than a fallback."""
        return self._uid_from_mac

    @override
    async def _async_setup(self) -> None:
        """Connect to the hub and build the model."""
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
            ) from err
        except (OSError, ConnectionError, HabitronError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connect_error",
            ) from err

    async def _async_connect_and_build(self) -> None:
        """Resolve, connect, build both models and register the devices."""
        self.host = await self._async_resolve_host()
        integration = await async_get_integration(self.hass, DOMAIN)
        if integration.version is not None:
            self._hbtn_version = str(integration.version)

        # Only probes the host; the client opens a socket per command.
        self._client = HabitronClient(self.host, _BUS_PORT)
        await self._client.connect()

        self.hub = await async_build_hub(self._client)
        await self._async_resolve_uid()
        self.base_url = self._resolve_base_url()
        self._register_hub_device()

        # The build needs the hub's event server stopped; restart it in any case.
        try:
            await self.client.reinit_hub(0)
            self.router = await async_build_system(self.client, b_uid=self.uid)
            await self._register_bus_devices()
        finally:
            await self.client.reinit_hub(1)

    async def _async_resolve_host(self) -> str:
        """Return the IP address to reach the hub at."""
        host: str = self.entry.data[CONF_HOST]
        if _is_ipv4(host):
            return host
        if host == CONF_DEFAULT_HOST:
            return await self.hass.async_add_executor_job(get_own_ip)
        return await get_host_ip(host)

    async def _async_resolve_uid(self) -> None:
        """Check the hub belongs to this entry and key the entry by its MAC."""
        self._uid_from_mac = bool(self.hub.uid)
        if not self._uid_from_mac:
            self.hub.uid = self.entry.unique_id or self.entry.entry_id
            _LOGGER.debug("Hub reported no usable MAC; using %s as uid", self.uid)
            return

        # Only the LAN MAC identifies a hub.
        hub_macs = {self.uid}

        if (bound := async_hub_macs(self.hass, self.entry)) and bound.isdisjoint(
            hub_macs
        ):
            # Another hub answers at the stored address, e.g. after a DHCP change.
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="wrong_hub",
                translation_placeholders={
                    "host": self.host,
                    "expected": min(bound),
                    "found": self.uid,
                },
            )
        # Replace an ignored entry for this hub, as a config flow would.
        for ignored in self.hass.config_entries.async_entries(
            DOMAIN, include_ignore=True
        ):
            if ignored.source == SOURCE_IGNORE and ignored.unique_id == self.uid:
                await self.hass.config_entries.async_remove(ignored.entry_id)

        # No await from here on, or a concurrent setup could pass the check too.
        if any(
            not bound_elsewhere.isdisjoint(hub_macs)
            for other in self.hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != self.entry.entry_id
            and other.source != SOURCE_IGNORE
            and (bound_elsewhere := async_hub_macs(self.hass, other))
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="duplicate_hub",
                translation_placeholders={"host": self.host, "uid": self.uid},
            )
        if self.entry.unique_id != self.uid:
            _LOGGER.debug(
                "Adopting hub identity for %s: %s -> %s",
                self.entry.title,
                self.entry.unique_id,
                self.uid,
            )
            self.hass.config_entries.async_update_entry(self.entry, unique_id=self.uid)

    def _resolve_base_url(self) -> str:
        """Return the base URL of the hub's own web UI."""
        if self.hub.is_addon:
            # The app panel also works when the add-on is not in the sidebar.
            return f"homeassistant://app/{self.hub.slug}"
        return f"http://{self.host}:{_WEB_PORT}"

    def _conf_url(self, path: str) -> str | None:
        """Return the link to ``path`` in the hub's own web UI."""
        if not self.host:
            return None
        if self.hub.is_addon:
            return f"{self.base_url}?index={quote(path, safe='')}"
        return f"{self.base_url}{path}"

    def _register_hub_device(self) -> None:
        """Register the SmartHub itself as a device."""
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            configuration_url=self._conf_url("/hub"),
            connections={(dr.CONNECTION_NETWORK_MAC, mac) for mac in self.hub.macs},
            identifiers={(DOMAIN, self.uid)},
            manufacturer=MANUFACTURER,
            suggested_area="House",
            name=self.smhub_name,
            model=self.hub.platform,
            sw_version=self.hub.version,
        )

    async def _register_bus_devices(self) -> None:
        """Register the router + module devices and push their registry ids."""
        dev_reg = dr.async_get(self.hass)
        router = self.router

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
        """Poll the bus and the hub, updating the model in place."""
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
            ) from err
        except HabitronError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_protocol_error",
            ) from err
        await self._async_update_host()
        self._update_router_issue()
        return HbtnData(
            crc=self.crc,
            host_readings_ok=self.host_readings_ok,
            sys_ok=self.router.sys_ok,
        )

    async def _async_update_host(self) -> None:
        """Refresh the hub's host readings without failing the update."""
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
        """Delete this entry's router repair issue."""
        ir.async_delete_issue(
            self.hass, DOMAIN, f"router_system_error_{self.router.uid}"
        )

    def _update_router_issue(self) -> None:
        """Raise or clear the repair issue for a router system error."""
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
        """Close the bus client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
