"""Add entities for UniFi devices once the controller adopts them."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from aiounifi.interfaces.api_handlers import ItemEvent, UnsubscribeType

from homeassistant.core import callback

from ..entity import async_device_supported_fn

if TYPE_CHECKING:
    from .hub import UnifiHub


class UnifiDeviceAdoption:
    """Track the devices the controller lists but has not adopted.

    Entities are only created on added events, so a device first seen
    pending adoption, or forgotten and adopted again, would stay without
    entities until the integration is reloaded. Only devices pending
    adoption are followed for changes.
    """

    def __init__(self, hub: UnifiHub) -> None:
        """Watch for devices pending adoption."""
        self.hub = hub
        self._add_entities_callbacks: list[Callable[[], None]] = []
        self._pending: dict[str, UnsubscribeType] = {}
        """Subscriptions to the followed devices, by MAC address."""
        hub.config.entry.async_on_unload(
            hub.api.devices.subscribe(self._async_device_added, ItemEvent.ADDED)
        )
        hub.config.entry.async_on_unload(self._unfollow_all)

    @callback
    def async_on_adoption(self, add_entities: Callable[[], None]) -> None:
        """Rerun adding entities for known objects once a device is adopted."""
        self._add_entities_callbacks.append(add_entities)

    @callback
    def async_follow_if_unadopted(self, obj_id: str) -> None:
        """Follow the device of an object if the controller lists it unadopted.

        Objects that do not belong to a device, like clients, are ignored.
        """
        mac = obj_id.partition("_")[0]
        if mac in self.hub.api.devices and not async_device_supported_fn(self.hub, mac):
            self._follow(mac)

    @callback
    def _async_device_added(self, event: ItemEvent, obj_id: str) -> None:
        """Follow a device that is listed as pending adoption."""
        if not async_device_supported_fn(self.hub, obj_id):
            self._follow(obj_id)

    @callback
    def _follow(self, mac: str) -> None:
        """Watch a pending device for its adoption."""
        if mac in self._pending:
            return
        self._pending[mac] = self.hub.api.devices.subscribe(
            self._async_pending_device_changed, ItemEvent.CHANGED, id_filter=mac
        )

    @callback
    def _unfollow_all(self) -> None:
        """Stop watching the devices still pending adoption."""
        for unsubscribe in self._pending.values():
            unsubscribe()
        self._pending.clear()

    @callback
    def _async_pending_device_changed(self, event: ItemEvent, obj_id: str) -> None:
        """Add entities once a followed device is adopted."""
        if not async_device_supported_fn(self.hub, obj_id):
            return
        self._pending.pop(obj_id)()
        # aiounifi processes the ports and outlets of this update after this
        # callback, and their entities are only created on added events
        self.hub.hass.loop.call_soon(self._async_add_entities)

    @callback
    def _async_add_entities(self) -> None:
        """Add entities for all known objects."""
        for add_entities in self._add_entities_callbacks:
            add_entities()
