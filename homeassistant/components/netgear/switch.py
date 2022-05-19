"""Support for Netgear switches."""
from collections.abc import Callable
from dataclasses import dataclass
import logging
from datetime import timedelta

from pynetgear import ALLOW, BLOCK

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR, KEY_ROUTER
from .router import NetgearDeviceEntity, NetgearRouter, NetgearRouterEntity

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
        update=lambda router: router._api.get_block_device_enable_status,
        action=lambda router: router._api.set_block_device_enable,
    )
]

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
    
    # Router entities
    router_entities = []

    for description in ROUTER_SWITCH_TYPES:
        router_entities.append(
            NetgearRouterSwitchEntity(router, description)
        )

    async_add_entities(router_entities, True)

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

        if new_entities:
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
        self._name = f"{self.get_device_name()} {self.entity_description.name}"
        self._unique_id = f"{self._mac}-{self.entity_description.key}"
        self._state = None
        self.async_update_device()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._router.async_allow_block_device(self._mac, ALLOW)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._router.async_allow_block_device(self._mac, BLOCK)
        await self.coordinator.async_request_refresh()

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        if self._device[self.entity_description.key] is None:
            self._state = None
        else:
            self._state = self._device[self.entity_description.key] == "Allow"


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
        self._name = f"{router.device_name} {entity_description.name}"
        self._unique_id = f"{router.serial_number}-{entity_description.key}"

        self._state = None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_update(self):
        """Poll the state of the switch."""
        async with self._router._api_lock:
            self._state = await self.hass.async_add_executor_job(self.entity_description.update(self._router))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        async with self._router._api_lock:
            await self.hass.async_add_executor_job(self.entity_description.action(self._router), True)
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        async with self._router._api_lock:
            await self.hass.async_add_executor_job(self.entity_description.action(self._router), False)
        self.async_schedule_update_ha_state(force_refresh=True)
