"""Binary sensor platform for UniFi Network integration.

Support for WAN status binary sensors of gateway devices.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import ApiItem
from aiounifi.models.device import Device

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)
from .hub import UnifiHub


@callback
def async_device_wan_status_supported_fn(
    wan_name: str,
    hub: UnifiHub,
    obj_id: str,
) -> bool:
    """Determine if device has the specific WAN interface."""
    wan_index = wan_name.removeprefix("WAN") or "1"
    return f"wan{wan_index}" in hub.api.devices[obj_id].raw


@callback
def async_device_wan_status_is_on_fn(
    wan_name: str,
    hub: UnifiHub,
    device: Device,
) -> bool | None:
    """Determine if WAN interface is online."""
    if last_wan_status := device.last_wan_status:
        status = last_wan_status.get(wan_name)
        if status is not None:
            return status == "online"
    return None


@dataclass(frozen=True, kw_only=True)
class UnifiBinarySensorEntityDescription[
    HandlerT: APIHandler, ApiItemT: ApiItem
](BinarySensorEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]):
    """Class describing UniFi binary sensor entity."""

    is_on_fn: Callable[[UnifiHub, ApiItemT], bool | None]


def make_wan_status_sensors() -> (
    tuple[UnifiBinarySensorEntityDescription, ...]
):
    """Create WAN status binary sensors."""
    sensors: list[UnifiBinarySensorEntityDescription] = []

    # WAN status names (WAN, WAN2, ...) map to API keys (wan1, wan2, ...).
    # Extras are filtered out per-device by supported_fn.
    wans = tuple((f"WAN{i}" if i > 1 else "WAN") for i in range(1, 7))

    for wan_name in wans:
        wan_slug = wan_name.lower()

        sensors.append(
            UnifiBinarySensorEntityDescription[Devices, Device](
                key=f"{wan_name} status",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=False,
                api_handler_fn=lambda api: api.devices,
                available_fn=async_device_available_fn,
                device_info_fn=async_device_device_info_fn,
                is_on_fn=partial(async_device_wan_status_is_on_fn, wan_name),
                name_fn=lambda device, _wn=wan_name: f"{_wn} Status",
                object_fn=lambda api, obj_id: api.devices[obj_id],
                supported_fn=partial(
                    async_device_wan_status_supported_fn, wan_name
                ),
                unique_id_fn=lambda hub, obj_id, _ws=wan_slug: (
                    f"wan_status-{_ws}-{obj_id}"
                ),
            )
        )

    return tuple(sensors)


ENTITY_DESCRIPTIONS: tuple[UnifiBinarySensorEntityDescription, ...] = ()

ENTITY_DESCRIPTIONS += make_wan_status_sensors()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, UnifiBinarySensorEntity, ENTITY_DESCRIPTIONS
    )


class UnifiBinarySensorEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], BinarySensorEntity
):
    """Base representation of a UniFi binary sensor."""

    entity_description: UnifiBinarySensorEntityDescription[HandlerT, ApiItemT]

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
        description = self.entity_description
        obj = description.object_fn(self.api, self._obj_id)
        if (is_on := description.is_on_fn(self.hub, obj)) != self.is_on:
            self._attr_is_on = is_on
