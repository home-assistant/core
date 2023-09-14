"""Button platform for UniFi Network integration.

Support for restarting UniFi devices.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import ApiItemT
from aiounifi.models.device import Device, DeviceRestartRequest

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .controller import UniFiController
from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)


@callback
async def async_restart_device_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Restart device."""
    await api.request(DeviceRestartRequest.create(obj_id))


@dataclass
class UnifiButtonEntityDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]


@dataclass
class UnifiButtonEntityDescription(
    ButtonEntityDescription,
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiButtonEntityDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi button entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiButtonEntityDescription, ...] = (
    UnifiButtonEntityDescription[Devices, Device](
        key="Device restart",
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        device_class=ButtonDeviceClass.RESTART,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        control_fn=async_restart_device_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda _: "Restart",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"device_restart-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform for UniFi Network integration."""
    UniFiController.register_platform(
        hass,
        config_entry,
        async_add_entities,
        UnifiButtonEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiButtonEntity(UnifiEntity[HandlerT, ApiItemT], ButtonEntity):
    """Base representation of a UniFi image."""

    entity_description: UnifiButtonEntityDescription[HandlerT, ApiItemT]

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.control_fn(self.controller.api, self._obj_id)

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
