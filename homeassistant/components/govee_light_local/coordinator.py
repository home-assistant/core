"""Coordinator for Govee light local."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Self, override

from govee_local_api import GoveeController, GoveeDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    CONF_DEVICE_IP,
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DOMAIN,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

type GoveeLocalConfigEntry = ConfigEntry[GoveeLocalApiCoordinator]


@dataclass
class GoveeLocalApiConfig:
    """Govee light local configuration."""

    manual_devices: set[str]

    @classmethod
    def from_config_entry(cls, config_entry: GoveeLocalConfigEntry) -> Self:
        """Return Govee light local configuration from config entry."""

        return cls(
            {
                subentry.data[CONF_DEVICE_IP]
                for subentry in config_entry.get_subentries_of_type(
                    SUBENTRY_TYPE_DEVICE
                )
            }
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


class GoveeLocalApiCoordinator(DataUpdateCoordinator[list[GoveeDevice]]):
    """Govee light local coordinator."""

    config_entry: GoveeLocalConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoveeLocalConfigEntry,
        listening_addresses: list[str],
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="GoveeLightLocalApi",
            update_interval=SCAN_INTERVAL,
        )

        # A single controller listens on every enabled address: it opens one
        # transport per address internally, so there is no need for one
        # controller per network interface.
        self._controller = GoveeController(
            loop=hass.loop,
            logger=_LOGGER,
            listening_addresses=listening_addresses,
            broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
            broadcast_port=CONF_TARGET_PORT_DEFAULT,
            listening_port=CONF_LISTENING_PORT_DEFAULT,
            discovery_enabled=True,
            discovery_interval=CONF_DISCOVERY_INTERVAL_DEFAULT,
            discovered_callback=None,
            update_enabled=False,
        )
        self._rebind_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the Govee coordinator."""

        # Home Assistant enumerates adapters once at startup, so an address can
        # be stale by the time we bind it. Keep the adapters that do bind.
        await self._controller.start(require_all=False)
        self._controller.send_update_message()
        log_bound_addresses(self._controller)

    @callback
    def set_discovery_callback(
        self, discovery_callback: Callable[[GoveeDevice, bool], bool]
    ) -> None:
        """Set discovery callback for automatic Govee light discovery."""
        self._controller.set_device_discovered_callback(discovery_callback)

    def add_device_to_discovery_queue(self, ip: str) -> bool:
        """Add a device by IP address to discovery queue."""
        return self._controller.add_device_to_discovery_queue(ip)

    def remove_device_from_discovery_queue(self, ip: str) -> None:
        """Remove a device by IP address from manual discovery queue."""
        self._controller.remove_device_from_discovery_queue(ip)

    def remove_device(self, device: GoveeDevice) -> None:
        """Remove a device from the controller."""
        self._controller.remove_device(device)

    def get_device_by_ip(self, ip: str) -> GoveeDevice | None:
        """Return a device by IP address."""
        return self._controller.get_device_by_ip(ip)

    @property
    def manual_device_ips(self) -> set[str]:
        """Return the IPs the controller tracks as manually added.

        A queued IP moves into ``devices`` with ``is_manual`` set once the
        device answers, and eviction puts it back in the queue, so the two are
        disjoint and their union mirrors the configured manual devices.
        """
        return {device.ip for device in self.devices if device.is_manual} | set(
            self.discovery_queue
        )

    @callback
    def _async_subentry_id_for_ip(self, ip: str) -> str | None:
        """Return the id of the device subentry configured with this address."""
        return next(
            (
                subentry.subentry_id
                for subentry in self.config_entry.get_subentries_of_type(
                    SUBENTRY_TYPE_DEVICE
                )
                if subentry.data[CONF_DEVICE_IP] == ip
            ),
            None,
        )

    @callback
    def _async_owned_subentry_id(self, device: GoveeDevice) -> str | None:
        """Return the id of the surviving subentry whose registry device is this lamp."""
        device_registry = dr.async_get(self.hass)
        if (
            (
                device_entry := device_registry.async_get_device_by_identifier(
                    (DOMAIN, device.fingerprint), self.config_entry.entry_id
                )
            )
            is not None
            and (subentry_id := device_entry.config_subentry_id) is not None
            and subentry_id in self.config_entry.subentries
        ):
            return subentry_id
        return None

    @callback
    def async_claim_subentry(self, device: GoveeDevice) -> str | None:
        """Claim the subentry the device belongs to, if any.

        The lamp keeps the subentry its registry entry already belongs to,
        even when its cached address differs: the address is only the hint
        for finding the lamp. An unowned lamp claims the subentry configured
        with its address, unless that subentry's registry device is another
        lamp; then it stays an ordinary device on the main entry.
        """
        if (owned_subentry_id := self._async_owned_subentry_id(device)) is not None:
            device.is_manual = True
            return owned_subentry_id

        subentry_id = self._async_subentry_id_for_ip(device.ip)
        if subentry_id is None:
            return None

        device_registry = dr.async_get(self.hass)
        # Claiming a subentry that already owns another lamp's registry entry
        # would put two lamps under one subentry and make either deletion
        # cascade to both.
        for entry in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            if (
                entry.config_subentry_id == subentry_id
                and (DOMAIN, device.fingerprint) not in entry.identifiers
            ):
                if device.is_manual:
                    # The library marks whatever answers a queued probe.
                    device.is_manual = False
                return None

        device.is_manual = True
        return subentry_id

    @callback
    def async_adopt_device(self, device: GoveeDevice) -> str | None:
        """Claim an already-discovered device for its manual subentry.

        Marks it manual so eviction re-queues it instead of dropping it, and
        moves its registrations under the subentry so deleting the subentry
        cascades to them. Entities move first: changing the device's subentry
        purges entities still pointing at the old one.

        Returns the id of the subentry the device belongs to afterwards.
        """
        if (subentry_id := self.async_claim_subentry(device)) is None:
            return None

        device_registry = dr.async_get(self.hass)
        if (
            device_entry := device_registry.async_get_device_by_identifier(
                (DOMAIN, device.fingerprint), self.config_entry.entry_id
            )
        ) is None or device_entry.config_subentry_id == subentry_id:
            return subentry_id

        entity_registry = er.async_get(self.hass)
        for entity in er.async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        ):
            entity_registry.async_update_entity(
                entity.entity_id, config_subentry_id=subentry_id
            )
        device_registry.async_update_device(
            device_entry.id, new_config_subentry_id=subentry_id
        )
        return subentry_id

    @callback
    def async_reconcile_subentries(self) -> None:
        """Align the probe queue and lamp ownership with the device subentries.

        The queue is derived state: exactly the configured addresses whose
        subentry's own lamp has not answered there. A lamp found at a
        configured address is claimed on the way. Runs on configuration
        changes and on every poll, so event-order races, such as a probe the
        library consumed for another subentry's lamp, heal within one scan
        interval.
        """
        desired: set[str] = set()
        for subentry in self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE):
            ip = subentry.data[CONF_DEVICE_IP]
            device = self.get_device_by_ip(ip)
            if (
                device is None
                or self.async_adopt_device(device) != subentry.subentry_id
            ):
                desired.add(ip)
        for ip in self.discovery_queue - desired:
            self.remove_device_from_discovery_queue(ip)
        for ip in desired - self.discovery_queue:
            self.add_device_to_discovery_queue(ip)

    @callback
    def async_remove_manual_device(self, ip: str) -> None:
        """Remove a manually added device and its registry entry."""
        # A non-manual device at this address was never claimed by the
        # subentry (its probe was still pending), so only the probe is dropped.
        if (device := self.get_device_by_ip(ip)) is not None and device.is_manual:
            device_registry = dr.async_get(self.hass)
            if entry := device_registry.async_get_device_by_identifier(
                (DOMAIN, device.fingerprint), self.config_entry.entry_id
            ):
                # Removing the device cascades to its entities.
                device_registry.async_remove_device(entry.id)
            # The registry removal event may already have made the controller
            # forget the device, so only remove it if it is still tracked.
            if self.get_device_by_ip(ip) is not None:
                self.remove_device(device)
        self.remove_device_from_discovery_queue(ip)

    async def async_cleanup(self) -> None:
        """Stop the controller and wait for its sockets to close."""

        # Wait for a running rebind, so cleanup() does not race a bind in flight.
        await self.async_wait_rebind()
        await async_cleanup_controller(self._controller)

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

    @property
    def discovery_queue(self) -> set[str]:
        """Return a set of devices in the discovery queue."""
        return self._controller.discovery_queue

    async def async_rebind_failed_addresses(self, _now: datetime) -> None:
        """Retry the addresses that did not bind."""
        async with self._rebind_lock:
            # Losing every endpoint is handled by the update, which reloads the entry.
            if not self._controller.bind_failures or not self._controller.protocols:
                return
            if await self._controller.rebind_failed():
                log_bound_addresses(self._controller)

    async def async_wait_rebind(self) -> None:
        """Wait for an in-flight rebind to finish."""
        async with self._rebind_lock:
            pass

    @override
    async def _async_update_data(self) -> list[GoveeDevice]:
        # A controller that lost every endpoint stays inoperative until restarted.
        if not self._controller.protocols:
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="no_live_endpoints"
            )
        self._controller.send_update_message()
        # The library only maintains the queue for unknown fingerprints, so
        # known lamps answering probes, address churn and eviction re-queues
        # all leave it stale; rederive it every poll.
        self.async_reconcile_subentries()
        return self.devices
