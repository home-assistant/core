"""Support for FluxLED/MagicHome switches."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FluxLedUpdateCoordinator
from .const import DOMAIN
from .entity import FluxOnOffEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FluxSwitch(
                coordinator,
                entry.unique_id,
                entry.data[CONF_NAME],
            )
        ]
    )


class FluxSwitch(FluxOnOffEntity, CoordinatorEntity, SwitchEntity):
    """Representation of a Flux switch."""

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on:
            await self._device.async_turn_on()
