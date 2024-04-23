"""Button platform for UniFi Network integration.

Support for restarting UniFi devices.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import secrets
from typing import Any

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.interfaces.ports import Ports
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItemT
from aiounifi.models.device import (
    Device,
    DevicePowerCyclePortRequest,
    DeviceRestartRequest,
)
from aiounifi.models.port import Port
from aiounifi.models.wlan import Wlan, WlanChangePasswordRequest

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
    async_wlan_available_fn,
    async_wlan_device_info_fn,
)
from .hub import UnifiHub


async def async_restart_device_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Restart device."""
    await api.request(DeviceRestartRequest.create(obj_id))


async def async_power_cycle_port_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Restart device."""
    mac, _, index = obj_id.partition("_")
    await api.request(DevicePowerCyclePortRequest.create(mac, int(index)))


async def async_regenerate_password_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Regenerate WLAN password."""
    await api.request(
        WlanChangePasswordRequest.create(obj_id, secrets.token_urlsafe(15))
    )


@dataclass(frozen=True, kw_only=True)
class UnifiButtonEntityDescription(
    ButtonEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi button entity."""

    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: tuple[UnifiButtonEntityDescription, ...] = (
    UnifiButtonEntityDescription[Devices, Device](
        key="Device restart",
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        control_fn=async_restart_device_control_fn,
        device_info_fn=async_device_device_info_fn,
        name_fn=lambda _: "Restart",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        unique_id_fn=lambda hub, obj_id: f"device_restart-{obj_id}",
    ),
    UnifiButtonEntityDescription[Ports, Port](
        key="PoE power cycle",
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
        api_handler_fn=lambda api: api.ports,
        available_fn=async_device_available_fn,
        control_fn=async_power_cycle_port_control_fn,
        device_info_fn=async_device_device_info_fn,
        name_fn=lambda port: f"{port.name} Power Cycle",
        object_fn=lambda api, obj_id: api.ports[obj_id],
        supported_fn=lambda hub, obj_id: bool(hub.api.ports[obj_id].port_poe),
        unique_id_fn=lambda hub, obj_id: f"power_cycle-{obj_id}",
    ),
    UnifiButtonEntityDescription[Wlans, Wlan](
        key="WLAN regenerate password",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.wlans,
        available_fn=async_wlan_available_fn,
        control_fn=async_regenerate_password_control_fn,
        device_info_fn=async_wlan_device_info_fn,
        name_fn=lambda wlan: "Regenerate Password",
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        unique_id_fn=lambda hub, obj_id: f"regenerate_password-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform for UniFi Network integration."""
    UnifiHub.get_hub(hass, config_entry).entity_loader.register_platform(
        async_add_entities,
        UnifiButtonEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiButtonEntity(UnifiEntity[HandlerT, ApiItemT], ButtonEntity):
    """Base representation of a UniFi button."""

    entity_description: UnifiButtonEntityDescription[HandlerT, ApiItemT]

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.control_fn(self.hub.api, self._obj_id)

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
