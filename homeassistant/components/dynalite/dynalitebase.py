"""Support for the Dynalite devices as entities."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.dynalite.bridge import DynaliteBridge
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
        if added_entities:
            async_add_entities(added_entities)

    bridge.register_add_devices(platform, async_add_entities_platform)


class DynaliteBase(Entity):
    """Base class for the Dynalite entities."""

    def __init__(self, device: Any, bridge: DynaliteBridge) -> None:
        """Initialize the base class."""
        self._device = device
        self._bridge = bridge
        self._unsub_dispatchers: list[Callable[[], None]] = []

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._device.name

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
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "name": self.name,
            "manufacturer": "Dynalite",
        }

    async def async_added_to_hass(self) -> None:
        """Added to hass so need to register to dispatch."""
        # register for device specific update
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

    async def async_will_remove_from_hass(self) -> None:
        """Unregister signal dispatch listeners when being removed."""
        for unsub in self._unsub_dispatchers:
            unsub()
        self._unsub_dispatchers = []
