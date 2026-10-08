"""Base entity for the Ampio integration."""

from typing import override

from ampio_mqtt import AmpioObject, AvailabilityChanged, ObjectRemoved, ObjectUpdated

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import AmpioData
from .const import DOMAIN


def _device_info(data: AmpioData, obj: AmpioObject) -> DeviceInfo:
    """Device info for the module owning ``obj``, or the M-SERV hub.

    Keyed on the module mac in the object's address, which both account
    tiers receive, so the grouping survives an account-tier switch. The
    admin-only module catalogue contributes metadata only, and every field is
    always passed so a tier downgrade degrades the whole device coherently.
    """
    if obj.is_server_owned:
        return DeviceInfo(identifiers={(DOMAIN, data.prefix)})
    mac = obj.address.mac
    module = data.admin.module_for(obj) if data.admin else None
    return DeviceInfo(
        identifiers={(DOMAIN, f"{data.prefix}:{mac}")},
        name=(module.nazwa_urzadzenia if module else None) or f"Ampio module 0x{mac:X}",
        manufacturer="Ampio",
        via_device_id=data.hub_device_id,
        model=module.model if module else None,
        sw_version=str(module.wersja_softu) if module else None,
        hw_version=str(module.wersja_pcb) if module else None,
        serial_number=str(module.mac_global) if module else None,
    )


class AmpioEntity(Entity):
    """Entity backed by one Ampio object."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, data: AmpioData, obj: AmpioObject) -> None:
        """Initialize from the discovery-time object snapshot."""
        self._data = data
        self._object_id = obj.id
        # Several Designer objects can drive one output and share its leaf.
        self._attr_unique_id = f"{data.prefix}_{obj.object_key}"
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
