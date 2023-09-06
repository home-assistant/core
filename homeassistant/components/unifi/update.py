"""Update entities for Ubiquiti network devices."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as UNIFI_DOMAIN
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)

if TYPE_CHECKING:
    from .controller import UniFiController

LOGGER = logging.getLogger(__name__)

_DataT = TypeVar("_DataT", bound=Device)
_HandlerT = TypeVar("_HandlerT", bound=Devices)


async def async_device_control_fn(api: aiounifi.Controller, obj_id: str) -> None:
    """Control upgrade of device."""
    await api.request(DeviceUpgradeRequest.create(obj_id))


@dataclass
class UnifiUpdateEntityDescriptionMixin(Generic[_HandlerT, _DataT]):
    """Validate and load entities from different UniFi handlers."""

    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]
    state_fn: Callable[[aiounifi.Controller, _DataT], bool]


@dataclass
class UnifiUpdateEntityDescription(
    UpdateEntityDescription,
    UnifiEntityDescription[_HandlerT, _DataT],
    UnifiUpdateEntityDescriptionMixin[_HandlerT, _DataT],
):
    """Class describing UniFi update entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiUpdateEntityDescription, ...] = (
    UnifiUpdateEntityDescription[Devices, Device](
        key="Upgrade device",
        device_class=UpdateDeviceClass.FIRMWARE,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        control_fn=async_device_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: None,
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        state_fn=lambda api, device: device.state == 4,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"device_update-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.register_platform_add_entities(
        UnifiDeviceUpdateEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class UnifiDeviceUpdateEntity(UnifiEntity[_HandlerT, _DataT], UpdateEntity):
    """Representation of a UniFi device update entity."""

    entity_description: UnifiUpdateEntityDescription[_HandlerT, _DataT]

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        self._attr_supported_features = UpdateEntityFeature.PROGRESS
        if self.controller.is_admin:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.entity_description.control_fn(self.controller.api, self._obj_id)

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update in_progress, installed_version and latest_version.
        """
        description = self.entity_description

        obj = description.object_fn(self.controller.api, self._obj_id)
        self._attr_in_progress = description.state_fn(self.controller.api, obj)
        self._attr_installed_version = obj.version
        self._attr_latest_version = obj.upgrade_to_firmware or obj.version
