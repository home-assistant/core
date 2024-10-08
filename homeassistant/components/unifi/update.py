"""Update entities for Ubiquiti network devices."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.models.device import Device, DeviceUpgradeRequest

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UnifiConfigEntry
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)

LOGGER = logging.getLogger(__name__)

_DataT = TypeVar("_DataT", bound=Device)
_HandlerT = TypeVar("_HandlerT", bound=Devices)


async def async_device_control_fn(api: aiounifi.Controller, obj_id: str) -> None:
    """Control upgrade of device."""
    await api.request(DeviceUpgradeRequest.create(obj_id))


@dataclass(frozen=True, kw_only=True)
class UnifiUpdateEntityDescription(
    UpdateEntityDescription, UnifiEntityDescription[_HandlerT, _DataT]
):
    """Class describing UniFi update entity."""

    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]
    state_fn: Callable[[aiounifi.Controller, _DataT], bool]


ENTITY_DESCRIPTIONS: tuple[UnifiUpdateEntityDescription, ...] = (
    UnifiUpdateEntityDescription[Devices, Device](
        key="Upgrade device",
        device_class=UpdateDeviceClass.FIRMWARE,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        control_fn=async_device_control_fn,
        device_info_fn=async_device_device_info_fn,
        object_fn=lambda api, obj_id: api.devices[obj_id],
        state_fn=lambda api, device: device.state == 4,
        unique_id_fn=lambda hub, obj_id: f"device_update-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiDeviceUpdateEntity,
        ENTITY_DESCRIPTIONS,
    )


class UnifiDeviceUpdateEntity(UnifiEntity[_HandlerT, _DataT], UpdateEntity):
    """Representation of a UniFi device update entity."""

    entity_description: UnifiUpdateEntityDescription[_HandlerT, _DataT]

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        self._attr_supported_features = UpdateEntityFeature.PROGRESS
        if self.hub.is_admin:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.entity_description.control_fn(self.api, self._obj_id)

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update in_progress, installed_version and latest_version.
        """
        description = self.entity_description

        obj = description.object_fn(self.api, self._obj_id)
        self._attr_in_progress = description.state_fn(self.api, obj)
        self._attr_installed_version = obj.version
        self._attr_latest_version = obj.upgrade_to_firmware or obj.version
