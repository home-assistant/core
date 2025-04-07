"""Support for INSTEON dimmers via PowerLinc Modem."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Insteon switches from a config entry."""

    @callback
    def async_add_insteon_switch_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.SWITCH,
            InsteonSwitchEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.SWITCH}"
    async_dispatcher_connect(hass, signal, async_add_insteon_switch_entities)
    async_add_insteon_devices(
        hass,
        Platform.SWITCH,
        InsteonSwitchEntity,
        async_add_entities,
    )


class InsteonSwitchEntity(InsteonEntity, SwitchEntity):
    """A Class for an Insteon switch entity."""

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self._insteon_device.async_on(group=self._insteon_device_group.group)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self._insteon_device.async_off(group=self._insteon_device_group.group)
