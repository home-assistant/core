"""Update entities for Ubiquiti network devices."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import CallbackType, ItemEvent, UnsubscribeType
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN

if TYPE_CHECKING:
    from aiounifi.models.event import EventKey

    from .controller import UniFiController

_DataT = TypeVar("_DataT", bound=Device)
_HandlerT = TypeVar("_HandlerT", bound=Devices)

Subscription = Callable[[CallbackType, ItemEvent], UnsubscribeType]

LOGGER = logging.getLogger(__name__)


@callback
def async_device_available_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if device is available."""
    device = controller.api.devices[obj_id]
    return controller.available and not device.disabled


async def async_device_control_fn(api: aiounifi.Controller, obj_id: str) -> None:
    """Control upgrade of device."""
    await api.request(DeviceUpgradeRequest.create(obj_id))


@callback
def async_device_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for device."""
    device = api.devices[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model,
        name=device.name or None,
        sw_version=device.version,
        hw_version=str(device.board_revision),
    )


@dataclass
class UnifiEntityLoader(Generic[_HandlerT, _DataT]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    api_handler_fn: Callable[[aiounifi.Controller], _HandlerT]
    available_fn: Callable[[UniFiController, str], bool]
    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]
    device_info_fn: Callable[[aiounifi.Controller, str], DeviceInfo]
    event_is_on: tuple[EventKey, ...] | None
    event_to_subscribe: tuple[EventKey, ...] | None
    name_fn: Callable[[_DataT], str | None]
    object_fn: Callable[[aiounifi.Controller, str], _DataT]
    state_fn: Callable[[aiounifi.Controller, _DataT], bool]
    supported_fn: Callable[[aiounifi.Controller, str], bool | None]
    unique_id_fn: Callable[[str], str]


@dataclass
class UnifiEntityDescription(
    UpdateEntityDescription, UnifiEntityLoader[_HandlerT, _DataT]
):
    """Class describing UniFi update entity."""

    custom_subscribe: Callable[[aiounifi.Controller], Subscription] | None = None


ENTITY_DESCRIPTIONS: tuple[UnifiEntityDescription, ...] = (
    UnifiEntityDescription[Devices, Device](
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
        state_fn=lambda api, device: device.state == 4,
        supported_fn=lambda api, obj_id: True,
        unique_id_fn=lambda obj_id: f"device_update-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    @callback
    def async_load_entities(description: UnifiEntityDescription) -> None:
        """Load and subscribe to UniFi devices."""
        entities: list[UpdateEntity] = []
        api_handler = description.api_handler_fn(controller.api)

        @callback
        def async_create_entity(event: ItemEvent, obj_id: str) -> None:
            """Create UniFi entity."""
            if not description.allowed_fn(
                controller, obj_id
            ) or not description.supported_fn(controller.api, obj_id):
                return

            entity = UnifiDeviceUpdateEntity(obj_id, controller, description)
            if event == ItemEvent.ADDED:
                async_add_entities([entity])
                return
            entities.append(entity)

        for obj_id in api_handler:
            async_create_entity(ItemEvent.CHANGED, obj_id)
        async_add_entities(entities)

        api_handler.subscribe(async_create_entity, ItemEvent.ADDED)

    for description in ENTITY_DESCRIPTIONS:
        async_load_entities(description)


class UnifiDeviceUpdateEntity(UpdateEntity, Generic[_HandlerT, _DataT]):
    """Representation of a UniFi device update entity."""

    entity_description: UnifiEntityDescription[_HandlerT, _DataT]
    _attr_should_poll = False

    def __init__(
        self,
        obj_id: str,
        controller: UniFiController,
        description: UnifiEntityDescription[_HandlerT, _DataT],
    ) -> None:
        """Set up UniFi update entity."""
        self._obj_id = obj_id
        self.controller = controller
        self.entity_description = description

        self._removed = False

        self._attr_supported_features = UpdateEntityFeature.PROGRESS
        if controller.site_role == "admin":
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        self._attr_available = description.available_fn(controller, obj_id)
        self._attr_device_info = description.device_info_fn(controller.api, obj_id)
        self._attr_unique_id = description.unique_id_fn(obj_id)

        obj = description.object_fn(self.controller.api, obj_id)
        self._attr_in_progress = description.state_fn(controller.api, obj)
        self._attr_name = description.name_fn(obj)
        self._attr_installed_version = obj.version
        self._attr_latest_version = obj.upgrade_to_firmware or obj.version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.entity_description.control_fn(self.controller.api, self._obj_id)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description
        handler = description.api_handler_fn(self.controller.api)
        self.async_on_remove(
            handler.subscribe(
                self.async_signalling_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_remove,
                self.remove_item,
            )
        )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the switch state."""
        if event == ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        description = self.entity_description
        obj = description.object_fn(self.controller.api, self._obj_id)
        self._attr_available = description.available_fn(self.controller, self._obj_id)
        self._attr_in_progress = description.state_fn(self.controller.api, obj)
        self._attr_installed_version = obj.version
        self._attr_latest_version = obj.upgrade_to_firmware or obj.version
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def remove_item(self, keys: set) -> None:
        """Remove entity if object ID is part of set."""
        if self._obj_id not in keys or self._removed:
            return
        self._removed = True
        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)
