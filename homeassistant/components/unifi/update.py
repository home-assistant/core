"""Update entities for Ubiquiti network devices."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, override

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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
    async_device_supported_fn,
)

LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


async def async_device_control_fn(api: aiounifi.Controller, obj_id: str) -> None:
    """Control upgrade of device."""
    await api.request(DeviceUpgradeRequest.create(obj_id))


@dataclass(frozen=True, kw_only=True)
class UnifiUpdateEntityDescription[_HandlerT: Devices, _DataT: Device](
    UpdateEntityDescription, UnifiEntityDescription[_HandlerT, _DataT]
):
    """Class describing UniFi update entity."""

    control_fn: (
        Callable[[aiounifi.Controller, str], Coroutine[Any, Any, None]] | None
    ) = None
    state_fn: Callable[[aiounifi.Controller, _DataT], bool]
    installed_version_fn: Callable[[_DataT], str | None] = lambda obj: obj.version
    latest_version_fn: Callable[[_DataT], str | None] = lambda obj: (
        obj.upgrade_to_firmware or obj.version
    )


def _str_or_none(value: int | None) -> str | None:
    """Return a version number as a string."""
    return None if value is None else str(value)


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
        supported_fn=async_device_supported_fn,
        unique_id_fn=lambda hub, obj_id: f"device_update-{obj_id}",
    ),
    UnifiUpdateEntityDescription[Devices, Device](
        key="Upgrade IPS engine",
        translation_key="ips_engine",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        object_fn=lambda api, obj_id: api.devices[obj_id],
        state_fn=lambda api, device: False,
        supported_fn=lambda hub, obj_id: (
            hub.api.devices[obj_id].suricata_version is not None
        ),
        unique_id_fn=lambda hub, obj_id: f"ips_engine-{obj_id}",
        installed_version_fn=lambda obj: _str_or_none(obj.suricata_version),
        # supported_suricata_version is not an installable target
        latest_version_fn=lambda obj: _str_or_none(
            obj.suricata_upgrade_pending_target or obj.suricata_version
        ),
    ),
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
        if self.entity_description.control_fn is not None and self.hub.is_admin:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        control_fn = self.entity_description.control_fn
        if TYPE_CHECKING:
            # Only entities with control_fn support INSTALL
            assert control_fn is not None
        try:
            await control_fn(self.api, self._obj_id)
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
        self._attr_installed_version = description.installed_version_fn(obj)
        self._attr_latest_version = description.latest_version_fn(obj)
