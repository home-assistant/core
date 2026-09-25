"""Button platform for UniFi Network integration.

Support for restarting UniFi devices.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import secrets
from typing import TYPE_CHECKING, Any, override

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.interfaces.ports import Ports
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItem
from aiounifi.models.device import (
    Device,
    DevicePowerCyclePortRequest,
    DeviceRestartRequest,
)
from aiounifi.models.port import Port
from aiounifi.models.wlan import Wlan, WlanChangePasswordRequest
from aiounifi.network.v1.interfaces.devices import Devices as NetworkDevices
from aiounifi.network.v1.interfaces.wifi_broadcasts import WifiBroadcasts
from aiounifi.network.v1.models.device import Device as NetworkDevice
from aiounifi.network.v1.models.wifi_broadcast import (
    PERSONAL_SECURITY_TYPES,
    WifiBroadcast,
)

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .coordinator import UnifiApiHandler
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
    async_network_device_available_fn,
    async_network_device_device_info_fn,
    async_wifi_broadcast_available_fn,
    async_wifi_broadcast_device_info_fn,
    async_wlan_available_fn,
    async_wlan_device_info_fn,
)

if TYPE_CHECKING:
    from .hub import UnifiHub

PARALLEL_UPDATES = 1


@callback
def async_port_power_cycle_available_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if port allows power cycle action."""
    if not async_device_available_fn(hub, obj_id):
        return False
    return bool(hub.api.ports[obj_id].poe_enable)


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


async def async_network_restart_device_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Restart a device of the Integration API."""
    await api.network.devices.restart(api.network.devices[obj_id].device_id)


async def async_network_regenerate_password_control_fn(
    api: aiounifi.Controller, obj_id: str
) -> None:
    """Give a WiFi broadcast of the Integration API a new passphrase."""
    await api.network.wifi_broadcasts.set_passphrase(obj_id, secrets.token_urlsafe(15))


@dataclass(frozen=True, kw_only=True)
class UnifiButtonEntityDescription[HandlerT: UnifiApiHandler, ApiItemT: ApiItem](
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
        object_fn=lambda api, obj_id: api.devices[obj_id],
        unique_id_fn=lambda hub, obj_id: f"device_restart-{obj_id}",
    ),
    UnifiButtonEntityDescription[Ports, Port](
        key="PoE power cycle",
        translation_key="port_power_cycle",
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
        api_handler_fn=lambda api: api.ports,
        available_fn=async_port_power_cycle_available_fn,
        control_fn=async_power_cycle_port_control_fn,
        device_info_fn=async_device_device_info_fn,
        object_fn=lambda api, obj_id: api.ports[obj_id],
        supported_fn=lambda hub, obj_id: bool(hub.api.ports[obj_id].port_poe),
        translation_placeholders_fn=lambda port: {"port_name": port.name},
        unique_id_fn=lambda hub, obj_id: f"power_cycle-{obj_id}",
    ),
    UnifiButtonEntityDescription[Wlans, Wlan](
        key="WLAN regenerate password",
        translation_key="wlan_regenerate_password",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.wlans,
        available_fn=async_wlan_available_fn,
        control_fn=async_regenerate_password_control_fn,
        device_info_fn=async_wlan_device_info_fn,
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        unique_id_fn=lambda hub, obj_id: f"regenerate_password-{obj_id}",
    ),
)


NETWORK_API_ENTITY_DESCRIPTIONS: tuple[UnifiButtonEntityDescription, ...] = (
    UnifiButtonEntityDescription[NetworkDevices, NetworkDevice](
        key="Device restart",
        entity_category=EntityCategory.CONFIG,
        device_class=ButtonDeviceClass.RESTART,
        api_handler_fn=lambda api: api.network.devices,
        available_fn=async_network_device_available_fn,
        control_fn=async_network_restart_device_control_fn,
        device_info_fn=async_network_device_device_info_fn,
        object_fn=lambda api, obj_id: api.network.devices[obj_id],
        supported_fn=lambda hub, obj_id: hub.api.network.devices[obj_id].supported,
        unique_id_fn=lambda hub, obj_id: f"device_restart-{obj_id}",
    ),
    UnifiButtonEntityDescription[WifiBroadcasts, WifiBroadcast](
        key="WLAN regenerate password",
        translation_key="wlan_regenerate_password",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.network.wifi_broadcasts,
        available_fn=async_wifi_broadcast_available_fn,
        control_fn=async_network_regenerate_password_control_fn,
        device_info_fn=async_wifi_broadcast_device_info_fn,
        object_fn=lambda api, obj_id: api.network.wifi_broadcasts[obj_id],
        supported_fn=lambda hub, obj_id: (
            hub.api.network.wifi_broadcasts[obj_id].security_type
            in PERSONAL_SECURITY_TYPES
        ),
        unique_id_fn=lambda hub, obj_id: f"regenerate_password-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button platform for UniFi Network integration."""
    hub = config_entry.runtime_data
    hub.entity_loader.register_platform(
        async_add_entities,
        UnifiButtonEntity,
        NETWORK_API_ENTITY_DESCRIPTIONS
        if hub.config.uses_api_key
        else ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiButtonEntity[HandlerT: UnifiApiHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], ButtonEntity
):
    """Base representation of a UniFi button."""

    entity_description: UnifiButtonEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_press(self) -> None:
        """Press the button."""
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
        """Update entity state."""
