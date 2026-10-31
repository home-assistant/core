"""Update entities for Ubiquiti network devices."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, override

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
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)
from .hub import UnifiHub

LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1

IPS_ENGINE_KEY = "IPS engine"


async def async_device_control_fn(api: aiounifi.Controller, obj_id: str) -> None:
    """Control upgrade of device."""
    await api.request(DeviceUpgradeRequest.create(obj_id))


@dataclass(frozen=True, kw_only=True)
class UnifiUpdateEntityDescription[_HandlerT: Devices, _DataT: Device](
    UpdateEntityDescription, UnifiEntityDescription[_HandlerT, _DataT]
):
    """Class describing UniFi update entity."""

    control_fn: Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]]
    state_fn: Callable[[aiounifi.Controller, _DataT], bool]


@dataclass(frozen=True, kw_only=True)
class UnifiIpsEngineUpdateEntityDescription(
    UpdateEntityDescription, UnifiEntityDescription[Devices, Device]
):
    """Class describing UniFi IPS engine update entity."""


@callback
def async_ips_engine_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Discover a reported IPS engine and keep a registered one through gaps."""
    if (IPS_ENGINE_KEY, obj_id) in hub.entity_loader.known_objects or (
        hub.api.devices[obj_id].suricata_version is not None
    ):
        return True
    registry = er.async_get(hub.hass)
    entity_id = registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, IPS_ENGINE_DESCRIPTION.unique_id_fn(hub, obj_id)
    )
    return (
        entity_id is not None
        and registry.entities[entity_id].config_entry_id == hub.config.entry.entry_id
    )


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

IPS_ENGINE_DESCRIPTION = UnifiIpsEngineUpdateEntityDescription(
    key=IPS_ENGINE_KEY,
    translation_key="ips_engine",
    entity_category=EntityCategory.DIAGNOSTIC,
    api_handler_fn=lambda api: api.devices,
    available_fn=async_device_available_fn,
    device_info_fn=async_device_device_info_fn,
    object_fn=lambda api, obj_id: api.devices[obj_id],
    supported_fn=async_ips_engine_supported_fn,
    unique_id_fn=lambda hub, obj_id: f"ips_engine-{obj_id}",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update entities for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiDeviceUpdateEntity,
        ENTITY_DESCRIPTIONS,
    )
    hub = config_entry.runtime_data
    hub.entity_loader.register_platform(
        async_add_entities, UnifiIpsEngineUpdateEntity, (IPS_ENGINE_DESCRIPTION,)
    )

    @callback
    def async_add_ips_engine_entity(event: ItemEvent, obj_id: str) -> None:
        """Add the IPS engine entity when a known gateway starts reporting it."""
        if (IPS_ENGINE_KEY, obj_id) not in hub.entity_loader.known_objects and (
            hub.api.devices[obj_id].suricata_version is not None
        ):
            async_add_entities(
                [UnifiIpsEngineUpdateEntity(obj_id, hub, IPS_ENGINE_DESCRIPTION)]
            )

    config_entry.async_on_unload(
        hub.api.devices.subscribe(async_add_ips_engine_entity, ItemEvent.CHANGED)
    )


class UnifiDeviceUpdateEntity[_HandlerT: Devices, _DataT: Device](
    UnifiEntity[_HandlerT, _DataT], UpdateEntity
):
    """Representation of a UniFi device update entity."""

    entity_description: UnifiUpdateEntityDescription[_HandlerT, _DataT]

    @callback
    @override
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        self._attr_supported_features = UpdateEntityFeature.PROGRESS
        if self.hub.is_admin:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        try:
            await self.entity_description.control_fn(self.api, self._obj_id)
        except aiounifi.AiounifiException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_request_failed",
            ) from err

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update in_progress, installed_version and latest_version.
        """
        description = self.entity_description

        obj = description.object_fn(self.api, self._obj_id)
        self._attr_in_progress = description.state_fn(self.api, obj)
        self._attr_installed_version = obj.version
        self._attr_latest_version = obj.upgrade_to_firmware or obj.version


class UnifiIpsEngineUpdateEntity(UnifiEntity[Devices, Device], UpdateEntity):
    """Read-only update entity for a gateway's Suricata IPS engine."""

    entity_description: UnifiIpsEngineUpdateEntityDescription
    _attr_title = "Suricata"

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update installed_version and latest_version."""
        obj = self.entity_description.object_fn(self.api, self._obj_id)
        installed = obj.suricata_version
        # supported_suricata_version is not an installable target
        latest = obj.suricata_upgrade_pending_target or installed
        self._attr_installed_version = None if installed is None else str(installed)
        self._attr_latest_version = None if latest is None else str(latest)
