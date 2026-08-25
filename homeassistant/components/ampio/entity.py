"""Base entity for the Ampio integration."""

from collections.abc import Iterator
from typing import override

from ampio_mqtt import (
    AmpioClient,
    AmpioObject,
    AvailabilityChanged,
    ObjectRemoved,
    ObjectUpdated,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import AmpioData
from .const import DOMAIN


def eligible_objects(client: AmpioClient) -> Iterator[AmpioObject]:
    """The objects any platform may expose as entities.

    ``visible`` is the M-SERV's own predicate for what the user still sees
    in Ampio Designer; ghost rows that survived removal fail it. A missing
    ``stable_key`` would otherwise leak into the unique_id.
    """
    return (
        obj
        for obj in client.objects.values()
        if obj.visible and obj.stable_key is not None
    )


def _opt_str(value: object | None) -> str | None:
    """Stringify a catalogue field, passing None through."""
    return None if value is None else str(value)


def _device_info(data: AmpioData, obj: AmpioObject) -> DeviceInfo:
    """Device info for the module owning ``obj``, or the M-SERV hub.

    Keyed on the leaf-derived module mac, which both account tiers receive,
    so the grouping survives an account-tier switch; the admin-only module
    catalogue contributes metadata only. Every catalogue-derived field is
    always passed so a tier downgrade degrades the whole device coherently
    instead of mixing the fallback name with stale metadata.
    """
    if obj.is_server_owned or (mac := obj.module_mac) is None:
        return DeviceInfo(identifiers={(DOMAIN, data.prefix)})
    module = data.client.module_for(obj)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{data.prefix}:{mac}")},
        name=(module.name if module else None) or f"Ampio module 0x{mac:X}",
        manufacturer="Ampio",
        via_device_id=data.hub_device_id,
        model=module.model if module else None,
        sw_version=_opt_str(module.sw_version) if module else None,
        hw_version=_opt_str(module.hw_version) if module else None,
        serial_number=_opt_str(module.mac_global) if module else None,
    )


class AmpioEntity(Entity):
    """Entity backed by one Ampio object."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, data: AmpioData, obj: AmpioObject) -> None:
        """Initialize from the discovery-time object snapshot."""
        self._data = data
        self._object_id = obj.id
        # ``stable_key`` survives a module swap; the prefix scopes it per server.
        self._attr_unique_id = f"{data.prefix}_{obj.stable_key}"
        self._attr_device_info = _device_info(data, obj)
        if obj.name:
            self._attr_name = obj.name

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the pushes that affect this entity's state."""
        client = self._data.client
        self.async_on_remove(
            client.subscribe(
                self._push_received,
                of=(ObjectUpdated, ObjectRemoved),
                object_id=self._object_id,
            )
        )
        self.async_on_remove(
            client.subscribe(self._push_received, of=AvailabilityChanged)
        )

    @callback
    def _push_received(
        self, event: ObjectUpdated | ObjectRemoved | AvailabilityChanged
    ) -> None:
        """Write state when the backing object or the connection changes."""
        self.async_write_ha_state()

    @property
    def _object(self) -> AmpioObject | None:
        """The backing object, or None once the catalogue dropped it."""
        return self._data.client.objects.get(self._object_id)

    @property
    @override
    def available(self) -> bool:
        """Available while the broker is connected and the object exists."""
        return self._data.client.available and self._object is not None
