"""Support for Netgear switches."""
import logging

from pynetgear import ALLOW, BLOCK

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR, KEY_ROUTER
from .router import NetgearDeviceEntity, NetgearRouter

_LOGGER = logging.getLogger(__name__)


SWITCH_TYPES = [
    SwitchEntityDescription(
        key="allow_or_block",
        name="Allowed on network",
        icon="mdi:block-helper",
        entity_category=EntityCategory.CONFIG,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
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
