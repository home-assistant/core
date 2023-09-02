"""Support for Netgear switches."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pynetgear import ALLOW, BLOCK

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR, KEY_ROUTER
from .entity import NetgearDeviceEntity, NetgearRouterEntity
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)

SWITCH_TYPES = [
    SwitchEntityDescription(
        key="allow_or_block",
        name="Allowed on network",
        icon="mdi:block-helper",
        entity_category=EntityCategory.CONFIG,
    )
]


@dataclass
class NetgearSwitchEntityDescriptionRequired:
    """Required attributes of NetgearSwitchEntityDescription."""

    update: Callable[[NetgearRouter], bool]
    action: Callable[[NetgearRouter], bool]


@dataclass
class NetgearSwitchEntityDescription(
    SwitchEntityDescription, NetgearSwitchEntityDescriptionRequired
):
    """Class describing Netgear Switch entities."""


ROUTER_SWITCH_TYPES = [
    NetgearSwitchEntityDescription(
        key="access_control",
        name="Access Control",
        icon="mdi:block-helper",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_block_device_enable_status,
        action=lambda router: router.api.set_block_device_enable,
    ),
    NetgearSwitchEntityDescription(
        key="traffic_meter",
        name="Traffic Meter",
        icon="mdi:wifi-arrow-up-down",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_traffic_meter_enabled,
        action=lambda router: router.api.enable_traffic_meter,
    ),
    NetgearSwitchEntityDescription(
        key="parental_control",
        name="Parental Control",
        icon="mdi:account-child-outline",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_parental_control_enable_status,
        action=lambda router: router.api.enable_parental_control,
    ),
    NetgearSwitchEntityDescription(
        key="qos",
        name="Quality of Service",
        icon="mdi:wifi-star",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_qos_enable_status,
        action=lambda router: router.api.set_qos_enable_status,
    ),
    NetgearSwitchEntityDescription(
        key="2g_guest_wifi",
        name="2.4G Guest Wifi",
        icon="mdi:wifi",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_2g_guest_access_enabled,
        action=lambda router: router.api.set_2g_guest_access_enabled,
    ),
    NetgearSwitchEntityDescription(
        key="5g_guest_wifi",
        name="5G Guest Wifi",
        icon="mdi:wifi",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_5g_guest_access_enabled,
        action=lambda router: router.api.set_5g_guest_access_enabled,
    ),
    NetgearSwitchEntityDescription(
        key="smart_connect",
        name="Smart Connect",
        icon="mdi:wifi",
        entity_category=EntityCategory.CONFIG,
        update=lambda router: router.api.get_smart_connect_enabled,
        action=lambda router: router.api.set_smart_connect_enabled,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]

    # Router entities
    router_entities = []

    for description in ROUTER_SWITCH_TYPES:
        router_entities.append(NetgearRouterSwitchEntity(router, description))

    async_add_entities(router_entities)

    # Entities per network device
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]
    tracked = set()

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        new_entities = []
        if not coordinator.data:
            return

        for mac, device in router.devices.items():
            if mac in tracked:
                continue

            new_entities.extend(
                [
                    NetgearAllowBlock(coordinator, router, device, entity_description)
                    for entity_description in SWITCH_TYPES
                ]
            )
            tracked.add(mac)

        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(new_device_callback))

    coordinator.data = True
    new_device_callback()


class NetgearAllowBlock(NetgearDeviceEntity, SwitchEntity):
    """Allow or Block a device from the network."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
        device: dict,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router, device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._mac}-{self.entity_description.key}"
        self._attr_is_on = None
        self.async_update_device()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._router.async_allow_block_device(self._mac, ALLOW)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._router.async_allow_block_device(self._mac, BLOCK)
        await self.coordinator.async_request_refresh()

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        if self._device[self.entity_description.key] is None:
            self._attr_is_on = None
        else:
            self._attr_is_on = self._device[self.entity_description.key] == "Allow"


class NetgearRouterSwitchEntity(NetgearRouterEntity, SwitchEntity):
    """Representation of a Netgear router switch."""

    _attr_entity_registry_enabled_default = False
    entity_description: NetgearSwitchEntityDescription

    def __init__(
        self,
        router: NetgearRouter,
        entity_description: NetgearSwitchEntityDescription,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(router)
        self.entity_description = entity_description
        self._attr_unique_id = f"{router.serial_number}-{entity_description.key}"

        self._attr_is_on = None
        self._attr_available = False

    async def async_added_to_hass(self):
        """Fetch state when entity is added."""
        await self.async_update()
        await super().async_added_to_hass()

    async def async_update(self):
        """Poll the state of the switch."""
        async with self._router.api_lock:
            response = await self.hass.async_add_executor_job(
                self.entity_description.update(self._router)
            )
        if response is None:
            self._attr_available = False
        else:
            self._attr_is_on = response
            self._attr_available = True

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        async with self._router.api_lock:
            await self.hass.async_add_executor_job(
                self.entity_description.action(self._router), True
            )

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        async with self._router.api_lock:
            await self.hass.async_add_executor_job(
                self.entity_description.action(self._router), False
            )
