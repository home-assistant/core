"""Support for the Dynalite devices as entities."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .bridge import DynaliteBridge
from .const import DOMAIN, LOGGER


def async_setup_entry_base(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    entity_from_device: Callable,
) -> None:
    """Record the async_add_entities function to add them later when received from Dynalite."""
    LOGGER.debug("Setting up %s entry = %s", platform, config_entry.data)
    bridge = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_entities_platform(devices):
        # assumes it is called with a single platform
        added_entities = []
        for device in devices:
            added_entities.append(entity_from_device(device, bridge))
        async_add_entities(added_entities)

    bridge.register_add_devices(platform, async_add_entities_platform)


class DynaliteBase(RestoreEntity, ABC):
    """Base class for the Dynalite entities."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: Any, bridge: DynaliteBridge) -> None:
        """Initialize the base class."""
        self._device = device
        self._bridge = bridge
        self._unsub_dispatchers: list[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return self._device.unique_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.available

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer="Dynalite",
            name=self._device.name,
        )

    async def async_added_to_hass(self) -> None:
        """Added to hass so need to restore state and register to dispatch."""
        # register for device specific update
        await super().async_added_to_hass()

        cur_state = await self.async_get_last_state()
        if cur_state:
            self.initialize_state(cur_state)
        else:
            LOGGER.info("Restore state not available for %s", self.entity_id)

        self._unsub_dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                self._bridge.update_signal(self._device),
                self.async_schedule_update_ha_state,
            )
        )
        # register for wide update
        self._unsub_dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                self._bridge.update_signal(),
                self.async_schedule_update_ha_state,
            )
        )

    @abstractmethod
    def initialize_state(self, state):
        """Initialize the state from cache."""

    async def async_will_remove_from_hass(self) -> None:
        """Unregister signal dispatch listeners when being removed."""
        for unsub in self._unsub_dispatchers:
            unsub()
        self._unsub_dispatchers = []
