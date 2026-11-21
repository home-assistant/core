"""Shared inbound UDP listener for BroadLink Magic gateways."""

import asyncio
from collections.abc import Callable
import logging

from broadlink_magic import (
    MSG_DISCOVERY,
    MSG_HEARTBEAT,
    DeviceKind,
    GatewaySet,
    InboundGatewayRegistry,
    unpack_header,
)

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_GATEWAY_LISTENER = f"{DOMAIN}_gateway_listener"
DATA_GATEWAY_LISTENER_LOCK = f"{DOMAIN}_gateway_listener_lock"


class GatewayListenerManager:
    """Own one fixed UDP listener and route imported gateway MACs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize an unbound listener manager."""
        self.hass = hass
        self.registry = InboundGatewayRegistry()
        self._entry_macs: dict[str, set[str]] = {}
        self._flows: set[str] = set()
        self._unsub_stop: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Bind the fixed Industry-compatible UDP port."""
        await self.registry.async_start()
        self._unsub_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
        )

    @callback
    def _async_handle_stop(self, _event: Event) -> None:
        """Close the listener when Home Assistant stops."""
        self._unsub_stop = None
        self.hass.async_create_task(
            self.async_close(), f"{DOMAIN} close gateway listener"
        )

    def acquire_flow(self, flow_id: str) -> None:
        """Keep the listener open while a Magic config flow is active."""
        self._flows.add(flow_id)

    async def async_release_flow(self, flow_id: str) -> None:
        """Release a Magic config flow listener reference."""
        self._flows.discard(flow_id)
        await self._async_close_if_unused()

    def register_gateway_set(
        self,
        entry_id: str,
        gateway_set: GatewaySet,
        on_update: Callable[[], None],
    ) -> None:
        """Register every imported gateway in one config entry.

        A gateway MAC routes to a single entry; MACs already owned by another
        entry are skipped so neither entry can replace or remove the other's
        route.
        """
        owned = {
            mac
            for other_entry_id, other_macs in self._entry_macs.items()
            if other_entry_id != entry_id
            for mac in other_macs
        }
        macs: set[str] = set()
        for gateway in gateway_set.gateways:
            if gateway.mac in owned:
                _LOGGER.warning(
                    "Gateway %s is already used by another BroadLink Magic family",
                    gateway.mac,
                )
            else:
                macs.add(gateway.mac)
        self._entry_macs[entry_id] = macs
        for mac in macs:

            def handle(
                data: bytes,
                addr: tuple[str, int],
                *,
                gateway_mac: str = mac,
            ) -> None:
                gateway = next(
                    item for item in gateway_set.gateways if item.mac == gateway_mac
                )
                previous_peer = gateway.peer
                gateway_set.handle_packet(gateway_mac, data, addr)
                on_update()
                try:
                    message_type, _sequence = unpack_header(data)
                except ValueError:
                    return
                if (
                    message_type in {MSG_DISCOVERY, MSG_HEARTBEAT}
                    and previous_peer != addr
                ):
                    self.hass.async_create_task(
                        self._async_query_devices(gateway_set),
                        f"{DOMAIN} query imported device status",
                    )

            self.registry.register(mac, handle)

    async def _async_query_devices(self, gateway_set: GatewaySet) -> None:
        """Query each state-reporting imported device after gateway reconnect."""
        for device in gateway_set.family.devices:
            if device.short_addr is not None and device.kind in {
                DeviceKind.AC,
                DeviceKind.CURTAIN,
                DeviceKind.LIGHT,
                DeviceKind.SWITCH,
                DeviceKind.PLUG,
            }:
                await gateway_set.send_status_query([device.short_addr])

    async def async_unregister_entry(self, entry_id: str) -> None:
        """Remove only the gateway routes owned by one entry."""
        for mac in self._entry_macs.pop(entry_id, set()):
            self.registry.unregister(mac)
        await self._async_close_if_unused()

    async def _async_close_if_unused(self) -> None:
        """Close and discard the listener when no flow or entry uses it.

        The check and the close run under the getter lock, so a setup that
        starts while the socket is closing waits and then binds a new listener
        instead of receiving this one.
        """
        async with _listener_lock(self.hass):
            if self._flows or self._entry_macs:
                return
            if self.hass.data.get(DATA_GATEWAY_LISTENER) is self:
                self.hass.data.pop(DATA_GATEWAY_LISTENER)
            await self.async_close()

    async def async_close(self) -> None:
        """Close the shared UDP listener."""
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None
        await self.registry.async_close()


def _listener_lock(hass: HomeAssistant) -> asyncio.Lock:
    return hass.data.setdefault(DATA_GATEWAY_LISTENER_LOCK, asyncio.Lock())


async def async_get_gateway_listener(
    hass: HomeAssistant,
) -> GatewayListenerManager:
    """Return the running hass-level gateway listener, binding it once."""
    async with _listener_lock(hass):
        if manager := hass.data.get(DATA_GATEWAY_LISTENER):
            return manager

        manager = GatewayListenerManager(hass)
        await manager.async_start()
        hass.data[DATA_GATEWAY_LISTENER] = manager
    return manager
