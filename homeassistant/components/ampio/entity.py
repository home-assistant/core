"""Base entity for the Ampio integration."""

from typing import override

from ampio_mqtt import (
    AmpioObject,
    AvailabilityChanged,
    ObjectRemoved,
    ObjectUpdated,
    format_mac,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import AmpioConfigEntry, AmpioData
from .const import DOMAIN


def _module_identifier(mac: int) -> tuple[str, str]:
    """The registry identifier of the module device on ``mac``."""
    return (DOMAIN, f"module:0x{mac:X}")


@callback
def _async_module_device_id(
    hass: HomeAssistant, entry: AmpioConfigEntry, obj: AmpioObject
) -> str:
    """Register the device of the module that owns ``obj`` and return its id.

    Keyed on the module mac in the object's address, which both account
    tiers receive. The admin-only module catalogue adds the name and the
    metadata, and each metadata field is always passed, so a tier downgrade
    clears all of it.
    """
    data = entry.runtime_data
    mac = obj.address.mac
    module = data.admin.module_for(obj) if data.admin else None
    device_info = dr.DeviceInfo(
        identifiers={_module_identifier(mac)},
        manufacturer="Ampio",
        via_device_id=data.hub_device_id,
        model=module.model if module else None,
        sw_version=str(module.wersja_softu) if module else None,
        hw_version=str(module.wersja_pcb) if module else None,
        serial_number=str(module.mac_global) if module else None,
    )
    if module is not None and module.nazwa_urzadzenia:
        device_info["name"] = module.nazwa_urzadzenia
    else:
        device_info["translation_key"] = "module"
        device_info["translation_placeholders"] = {"mac": format_mac(mac)}
    return (
        dr.async_get(hass)
        .async_get_or_create(config_entry_id=entry.entry_id, **device_info)
        .id
    )


@callback
def async_parent_device_id(
    hass: HomeAssistant, entry: AmpioConfigEntry, obj: AmpioObject
) -> str:
    """Return the device that the child device of ``obj`` hangs under.

    The registry refuses to re-parent a child device, so an object that moved
    to another module in Designer stays under its first parent. A module
    device is registered, or refreshed, only for the objects under it.
    """
    registry = dr.async_get(hass)
    child = registry.async_get_child_device_by_identifier(
        (DOMAIN, obj.object_key), entry.entry_id
    )
    if obj.is_server_owned:
        if child is not None:
            return child.parent_device_id
        return entry.runtime_data.hub_device_id
    module = registry.async_get_device_by_identifier(
        _module_identifier(obj.address.mac), entry.entry_id
    )
    if child is not None and (module is None or module.id != child.parent_device_id):
        return child.parent_device_id
    return _async_module_device_id(hass, entry, obj)


class AmpioEntity(Entity):
    """Entity backed by one Ampio object, on the object's own device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, data: AmpioData, obj: AmpioObject, parent_device_id: str
    ) -> None:
        """Initialize from the discovery-time object snapshot."""
        self._data = data
        self._object_id = obj.id
        # Several Designer objects can drive one output and share its leaf.
        self._attr_unique_id = obj.object_key
        device_info = dr.ChildDeviceInfo(
            identifiers={(DOMAIN, obj.object_key)},
            parent_device_id=parent_device_id,
        )
        if obj.name:
            device_info["name"] = obj.name
            self._attr_name = None
        else:
            device_info["translation_key"] = "object"
            device_info["translation_placeholders"] = {"id": str(obj.id)}
        self._attr_device_info = device_info

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
