"""Coordinator for Govee light local."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any, override

from govee_local_api import GoveeController, GoveeDevice

from homeassistant.components import network
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_FINGERPRINT,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    REBIND_INTERVAL,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NoListeningAddressesError(HomeAssistantError):
    """No enabled network adapter has an IPv4 address to listen on."""


@dataclass
class GoveeLocalData:
    """Coordinator shared by every config entry."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    coordinator: GoveeLocalApiCoordinator | None = None


# Every lamp answers on the same UDP port, so one controller serves every
# config entry rather than being owned by any one of them.
GOVEE_LOCAL_DATA: HassKey[GoveeLocalData] = HassKey(DOMAIN)


@dataclass
class GoveeLocalRuntimeData:
    """Runtime data of a Govee light local config entry."""

    coordinator: GoveeLocalApiCoordinator
    device: GoveeDevice


type GoveeLocalConfigEntry = ConfigEntry[GoveeLocalRuntimeData]


async def async_get_listening_addresses(hass: HomeAssistant) -> list[str]:
    """Get the enabled IPv4 source addresses, with network mask, for Govee local."""
    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        _LOGGER.debug(
            "Adapter %s (%s): %s",
            adapter["name"],
            "enabled" if adapter["enabled"] else "disabled",
            [f"{ipv4['address']}/{ipv4['network_prefix']}" for ipv4 in adapter["ipv4"]],
        )
    return sorted(
        {
            f"{ipv4['address']}/{ipv4['network_prefix']}"
            for adapter in adapters
            if adapter["enabled"]
            for ipv4 in adapter["ipv4"]
        }
    )


def _is_legacy_entry(entry: ConfigEntry) -> bool:
    """Return if the entry predates one entry per lamp."""
    return entry.unique_id is None or entry.unique_id == DOMAIN


@callback
def async_get_legacy_entry(hass: HomeAssistant) -> GoveeLocalConfigEntry | None:
    """Return the entry that is still to be split per lamp, unless it is disabled."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if _is_legacy_entry(entry) and not entry.disabled_by
        ),
        None,
    )


def log_bound_addresses(controller: GoveeController) -> None:
    """Log the addresses and networks the controller is bound to."""

    _LOGGER.debug(
        "Listening on port %d: %s",
        CONF_LISTENING_PORT_DEFAULT,
        ", ".join(
            f"{address} ({network})" if network else f"{address} (no network mask)"
            for address, network in zip(
                controller.listening_addresses, controller.networks, strict=True
            )
        ),
    )

    # The library already warns per failed bind; keep this at debug for the full picture.
    for address, error in controller.bind_failures:
        _LOGGER.debug("Not listening on %s: %s", address, error.strerror or error)


async def async_cleanup_controller(controller: GoveeController) -> None:
    """Close the controller's sockets and wait for the listening port to be released."""

    cleanup_complete = controller.cleanup(timeout=CLEANUP_TIMEOUT)
    try:
        async with asyncio.timeout(CLEANUP_WAIT_TIMEOUT):
            await cleanup_complete.wait()
    except TimeoutError:
        _LOGGER.warning(
            "Timed out waiting for port %d to be released", CONF_LISTENING_PORT_DEFAULT
        )


async def async_acquire_coordinator(hass: HomeAssistant) -> GoveeLocalApiCoordinator:
    """Return the shared coordinator, starting it for its first user.

    Raises NoListeningAddressesError or OSError if it cannot be started.
    """
    # No await between the lookup and the store, so concurrent callers share it.
    data = hass.data.setdefault(GOVEE_LOCAL_DATA, GoveeLocalData())
    async with data.lock:
        if (coordinator := data.coordinator) is None:
            listening_addresses = await async_get_listening_addresses(hass)
            _LOGGER.debug("Enabled listening addresses: %s", listening_addresses)
            if not listening_addresses:
                raise NoListeningAddressesError
            coordinator = GoveeLocalApiCoordinator(hass, listening_addresses)
            await coordinator.async_start()
            data.coordinator = coordinator
        coordinator.ref_count += 1
        return coordinator


async def async_release_coordinator(
    hass: HomeAssistant, coordinator: GoveeLocalApiCoordinator
) -> None:
    """Release the shared coordinator, stopping it after its last user."""
    data = hass.data[GOVEE_LOCAL_DATA]
    async with data.lock:
        coordinator.ref_count -= 1
        if coordinator.ref_count:
            return
        if data.coordinator is coordinator:
            data.coordinator = None
        await coordinator.async_stop()


class GoveeLocalApiCoordinator(DataUpdateCoordinator[list[GoveeDevice]]):
    """Govee light local coordinator."""

    config_entry: None

    def __init__(self, hass: HomeAssistant, listening_addresses: list[str]) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=None,  # It is shared between every config entry
            name="GoveeLightLocalApi",
            update_interval=SCAN_INTERVAL,
        )

        self._controller = GoveeController(
            loop=hass.loop,
            logger=_LOGGER,
            listening_addresses=listening_addresses,
            broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
            broadcast_port=CONF_TARGET_PORT_DEFAULT,
            listening_port=CONF_LISTENING_PORT_DEFAULT,
            discovery_enabled=True,
            discovery_interval=CONF_DISCOVERY_INTERVAL_DEFAULT,
            update_enabled=False,
        )
        self._controller.set_device_discovered_callback(self._async_device_discovered)
        self._rebind_lock = asyncio.Lock()
        self._unsub_rebind: CALLBACK_TYPE | None = None
        self._waiters: dict[str, asyncio.Future[GoveeDevice]] = {}
        self.ref_count = 0

    async def async_start(self) -> None:
        """Start the Govee coordinator."""

        try:
            # Home Assistant enumerates adapters once at startup, so an address
            # can be stale by the time we bind it. Keep the adapters that do bind.
            await self._controller.start(require_all=False)
        except OSError, asyncio.CancelledError:
            await async_cleanup_controller(self._controller)
            raise
        self._controller.send_update_message()
        log_bound_addresses(self._controller)
        self._unsub_rebind = async_track_time_interval(
            self.hass,
            self.async_rebind_failed_addresses,
            REBIND_INTERVAL,
            name="Govee light local rebind",
        )
        await self.async_register_shutdown()

    async def async_stop(self) -> None:
        """Stop the controller and wait for its sockets to close."""

        if self._unsub_rebind is not None:
            self._unsub_rebind()
            self._unsub_rebind = None
        await self.async_shutdown()
        # Wait for a running rebind, so cleanup() does not race a bind in flight.
        await self.async_wait_rebind()
        await async_cleanup_controller(self._controller)

    @callback
    def _async_device_discovered(self, device: GoveeDevice, is_new: bool) -> bool:
        """Handle a scan reply; return whether the lamp is to be tracked."""
        fingerprint = device.fingerprint
        if (waiter := self._waiters.get(fingerprint)) is not None and not waiter.done():
            waiter.set_result(device)

        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, fingerprint
        )
        if entry is not None and (entry.source == SOURCE_IGNORE or entry.disabled_by):
            # Left untracked, so it counts as new once that entry is removed.
            self._controller.remove_device(device)
            return False
        if entry is not None and entry.state is ConfigEntryState.LOADED:
            if entry.data[CONF_IP_ADDRESS] != device.ip:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_IP_ADDRESS: device.ip}
                )
        elif (
            is_new
            # For a retrying entry the flow aborts, stores the address and
            # retries the entry now.
            and (entry is None or entry.state is ConfigEntryState.SETUP_RETRY)
            # Its lamps are offered once it has become the entry of one of them.
            and async_get_legacy_entry(self.hass) is None
        ):
            self._async_create_flow(device)
        return True

    @property
    def unconfigured_devices(self) -> list[GoveeDevice]:
        """Return the tracked lamps that have no config entry."""
        return [
            device
            for device in self._controller.devices
            if self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, device.fingerprint
            )
            is None
        ]

    @callback
    def async_offer_unconfigured(self) -> None:
        """Offer the lamps without a config entry; a scan reply only does it once."""
        for device in self.unconfigured_devices:
            self._async_create_flow(device)

    @callback
    def _async_create_flow(self, device: GoveeDevice) -> None:
        """Offer a lamp to the user, or add it right away if it was set up before."""
        device_registry = dr.async_get(self.hass)
        owner = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if device_registry.async_get_device_by_identifier(
                    (DOMAIN, device.fingerprint), entry.entry_id
                )
            ),
            None,
        )
        if owner is not None and (owner.disabled_by or _is_legacy_entry(owner)):
            # Its entry is disabled, or adds its lamps itself once it is split.
            return
        discovery_flow.async_create_flow(
            self.hass,
            DOMAIN,
            context={
                "source": SOURCE_IMPORT if owner else SOURCE_INTEGRATION_DISCOVERY
            },
            data={
                CONF_IP_ADDRESS: device.ip,
                CONF_FINGERPRINT: device.fingerprint,
                CONF_MODEL: device.sku,
            },
        )

    async def async_wait_for_device(
        self, fingerprint: str, ip: str | None
    ) -> GoveeDevice | None:
        """Return the lamp once it answers a scan, probing its last known address."""
        if (
            device := self._controller.get_device_by_fingerprint(fingerprint)
        ) is not None:
            return device

        waiter = self._waiters[fingerprint] = self.hass.loop.create_future()
        if ip is not None:
            self._controller.add_device_to_discovery_queue(ip)
        # Queueing alone waits for the next discovery interval.
        self._controller.send_discovery_message()
        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                return await waiter
        except TimeoutError:
            return None
        finally:
            del self._waiters[fingerprint]
            # Dequeueing an address also makes the library forget a lamp
            # tracked there, which could be another entry's.
            if ip is not None and self._controller.get_device_by_ip(ip) is None:
                self._controller.remove_device_from_discovery_queue(ip)

    async def async_scan(self) -> list[GoveeDevice]:
        """Scan and return the answering lamps that had no config entry."""
        # Compared with the entries from before the scan, so a lamp that gets
        # its entry while the scan runs is still part of the result.
        configured = {
            entry.unique_id for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        started = dt_util.utcnow()
        self._controller.send_discovery_message()
        await asyncio.sleep(DISCOVERY_TIMEOUT)
        # A lamp stays tracked after it stops answering, so check it was heard.
        return [
            device
            for device in self._controller.devices
            if device.fingerprint not in configured and device.lastseen >= started
        ]

    @callback
    def remove_device(self, device: GoveeDevice) -> None:
        """Stop tracking a lamp, so its next scan reply is handled as a new one."""
        self._controller.remove_device(device)

    async def turn_on(self, device: GoveeDevice) -> None:
        """Turn on the light."""
        await device.turn_on()

    async def turn_off(self, device: GoveeDevice) -> None:
        """Turn off the light."""
        await device.turn_off()

    async def set_brightness(self, device: GoveeDevice, brightness: int) -> None:
        """Set light brightness."""
        await device.set_brightness(brightness)

    async def set_rgb_color(
        self, device: GoveeDevice, red: int, green: int, blue: int
    ) -> None:
        """Set light RGB color."""
        await device.set_rgb_color(red, green, blue)

    async def set_temperature(self, device: GoveeDevice, temperature: int) -> None:
        """Set light color in kelvin."""
        await device.set_temperature(temperature)

    async def set_scene(self, device: GoveeDevice, scene: str) -> None:
        """Set light scene."""
        await device.set_scene(scene)

    @property
    def devices(self) -> list[GoveeDevice]:
        """Return a list of discovered Govee devices."""

        return self._controller.devices

    async def async_rebind_failed_addresses(self, _now: datetime) -> None:
        """Retry the addresses that did not bind."""
        async with self._rebind_lock:
            # Losing every endpoint is handled by the update, which reloads the entries.
            if not self._controller.bind_failures or not self._controller.protocols:
                return
            if await self._controller.rebind_failed():
                log_bound_addresses(self._controller)

    async def async_wait_rebind(self) -> None:
        """Wait for an in-flight rebind to finish."""
        async with self._rebind_lock:
            pass

    def _polling_disabled(self) -> bool:
        """Return if every lamp's entry has polling disabled."""
        return all(
            entry.pref_disable_polling
            for entry in self.hass.config_entries.async_entries(
                DOMAIN, include_ignore=False, include_disabled=False
            )
        )

    @override
    @callback
    def _schedule_refresh(self) -> None:
        # Shared between the entries, so the base class cannot check their preference.
        if self._polling_disabled():
            return
        super()._schedule_refresh()

    @override
    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        remove_listener = super().async_add_listener(update_callback, context)
        # The base class only schedules for the first listener, which may
        # belong to an entry with polling disabled.
        self._schedule_refresh()
        return remove_listener

    @override
    async def _async_update_data(self) -> list[GoveeDevice]:
        # A controller that lost every endpoint stays inoperative until restarted.
        if not self._controller.protocols:
            # Detached, so the reloading entries start a new coordinator
            # instead of sharing this one again.
            data = self.hass.data[GOVEE_LOCAL_DATA]
            if data.coordinator is self:
                data.coordinator = None
            for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="no_live_endpoints"
            )
        self._controller.send_update_message()
        return self.devices
