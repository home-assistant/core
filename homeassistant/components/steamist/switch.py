"""Support for Steamist switches."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiosteamist import (
    MODEL_550,
    PROFILE_OFF,
    PROFILE_SHOWER_1,
    PROFILE_SHOWER_2,
    PROFILE_STEAM_1,
    PROFILE_STEAM_2,
    Steamist,
    SteamistStatus,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamistConfigEntry
from .entity import SteamistEntity


@dataclass(frozen=True, kw_only=True)
class SteamistSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Steamist switch entity."""

    is_on_fn: Callable[[SteamistStatus], bool]
    turn_on_fn: Callable[[Steamist], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Steamist], Coroutine[Any, Any, None]] = (
        lambda client: client.async_turn_off_steam()
    )


ACTIVE_SWITCH = SteamistSwitchEntityDescription(
    key="active",
    translation_key="steam_active",
    is_on_fn=lambda status: status.steam_active,
    turn_on_fn=lambda client: client.async_turn_on_steam(),
)

MODEL_550_SWITCHES: tuple[SteamistSwitchEntityDescription, ...] = (
    SteamistSwitchEntityDescription(
        key="shower_active",
        translation_key="shower_active",
        is_on_fn=lambda status: status.shower_active,
        turn_on_fn=lambda client: client.async_turn_on_shower(),
        turn_off_fn=lambda client: client.async_turn_off_shower(),
    ),
    SteamistSwitchEntityDescription(
        key="steam_profile_1",
        translation_key="steam_profile_1",
        is_on_fn=lambda status: status.profile == PROFILE_STEAM_1,
        turn_on_fn=lambda client: client.async_set_profile(PROFILE_STEAM_1),
        turn_off_fn=lambda client: client.async_set_profile(PROFILE_OFF),
    ),
    SteamistSwitchEntityDescription(
        key="steam_profile_2",
        translation_key="steam_profile_2",
        is_on_fn=lambda status: status.profile == PROFILE_STEAM_2,
        turn_on_fn=lambda client: client.async_set_profile(PROFILE_STEAM_2),
        turn_off_fn=lambda client: client.async_set_profile(PROFILE_OFF),
    ),
    SteamistSwitchEntityDescription(
        key="shower_profile_1",
        translation_key="shower_profile_1",
        is_on_fn=lambda status: status.profile == PROFILE_SHOWER_1,
        turn_on_fn=lambda client: client.async_set_profile(PROFILE_SHOWER_1),
        turn_off_fn=lambda client: client.async_set_profile(PROFILE_OFF),
    ),
    SteamistSwitchEntityDescription(
        key="shower_profile_2",
        translation_key="shower_profile_2",
        is_on_fn=lambda status: status.profile == PROFILE_SHOWER_2,
        turn_on_fn=lambda client: client.async_set_profile(PROFILE_SHOWER_2),
        turn_off_fn=lambda client: client.async_set_profile(PROFILE_OFF),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SteamistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = config_entry.runtime_data
    descriptions: list[SteamistSwitchEntityDescription] = [ACTIVE_SWITCH]
    if (
        config_entry.data.get(CONF_MODEL) == MODEL_550
        or coordinator.client.model == MODEL_550
    ):
        descriptions.extend(MODEL_550_SWITCHES)
    async_add_entities(
        [
            SteamistSwitchEntity(coordinator, config_entry, description)
            for description in descriptions
        ]
    )


class SteamistSwitchEntity(SteamistEntity, SwitchEntity):
    """Representation of a Steamist steam/shower switch."""

    entity_description: SteamistSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return if the switch is active."""
        return self.entity_description.is_on_fn(self._status)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()
