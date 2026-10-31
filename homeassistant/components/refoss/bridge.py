"""Refoss integration."""

from time import monotonic

from refoss_ha.device import DeviceInfo
from refoss_ha.device_manager import async_build_base_device
from refoss_ha.discovery import Discovery, Listener

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DISPATCH_DEVICE_DISCOVERED, LOGGER, SWEEP_COOLDOWN
from .coordinator import RefossDataUpdateCoordinator
from .probe import build_probe_addresses, networks_from_options

type RefossConfigEntry = ConfigEntry[DiscoveryService]


class DiscoveryService(Listener):
    """Discovery event handler for refoss devices."""

    def __init__(
        self, hass: HomeAssistant, config_entry: RefossConfigEntry, discovery: Discovery
    ) -> None:
        """Init discovery service."""
        self.hass = hass
        self.config_entry = config_entry

        self.discovery = discovery
        self.discovery.add_listener(self)

        self.coordinators: list[RefossDataUpdateCoordinator] = []
        self._last_sweep: float | None = None

    async def async_scan(self) -> None:
        """Probe the local network and any configured VLAN targets."""
        networks = networks_from_options(self.config_entry.options)
        local_broadcasts = [
            str(address)
            for address in await async_get_ipv4_broadcast_addresses(self.hass)
        ]
        addresses = build_probe_addresses(
            networks,
            local_broadcasts=local_broadcasts,
            known_ips=[device.inner_ip for device in self.discovery.devices],
            include_hosts=self._should_include_hosts(networks),
        )
        await self.discovery.broadcast_msg(addresses=addresses)

    def _should_include_hosts(self, networks: list[str]) -> bool:
        """Return whether this scan should unicast every host in configured networks.

        Sweeps run at startup and again after the cooldown, including when no device
        has been found yet. Bare IPv4 addresses are probed as-is and never expanded.
        """
        if not any("/" in network for network in networks):
            return False

        now = monotonic()
        if self._last_sweep is None or now - self._last_sweep >= SWEEP_COOLDOWN:
            self._last_sweep = now
            return True

        return False

    async def device_found(self, device_info: DeviceInfo) -> None:
        """Handle new device found on the network."""

        device = await async_build_base_device(device_info)
        if device is None:
            return

        coordo = RefossDataUpdateCoordinator(self.hass, self.config_entry, device)
        self.coordinators.append(coordo)
        await coordo.async_refresh()

        LOGGER.debug(
            "Discover new device: %s, ip: %s",
            device_info.dev_name,
            device_info.inner_ip,
        )
        async_dispatcher_send(self.hass, DISPATCH_DEVICE_DISCOVERED, coordo)

    async def device_update(self, device_info: DeviceInfo) -> None:
        """Handle updates in device information, update if ip has changed."""
        for coordinator in self.coordinators:
            if coordinator.device.device_info.mac == device_info.mac:
                LOGGER.debug(
                    "Update device %s ip to %s",
                    device_info.dev_name,
                    device_info.inner_ip,
                )
                coordinator.device.device_info.inner_ip = device_info.inner_ip
                await coordinator.async_refresh()
