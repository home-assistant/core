"""Support for Steamist switches."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SteamistConfigEntry
from .entity import SteamistEntity

ACTIVE_SWITCH = SwitchEntityDescription(
    key="active",
    translation_key="steam_active",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SteamistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = config_entry.runtime_data
    async_add_entities([SteamistSwitchEntity(coordinator, config_entry, ACTIVE_SWITCH)])


class SteamistSwitchEntity(SteamistEntity, SwitchEntity):
    """Representation of a Steamist steam switch."""

    @property
    @override
    def is_on(self) -> bool:
        """Return if the steam is active."""
        return self._status.active

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the steam on."""
        await self.coordinator.client.async_turn_on_steam()
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the steam off."""
        await self.coordinator.client.async_turn_off_steam()
        await self.coordinator.async_request_refresh()
