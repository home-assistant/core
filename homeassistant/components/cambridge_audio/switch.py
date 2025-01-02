"""Support for Cambridge Audio switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiostreammagic import StreamMagicClient

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CambridgeAudioConfigEntry
from .entity import CambridgeAudioEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CambridgeAudioSwitchEntityDescription(SwitchEntityDescription):
    """Describes Cambridge Audio switch entity."""

    value_fn: Callable[[StreamMagicClient], bool]
    set_value_fn: Callable[[StreamMagicClient, bool], Awaitable[None]]


CONTROL_ENTITIES: tuple[CambridgeAudioSwitchEntityDescription, ...] = (
    CambridgeAudioSwitchEntityDescription(
        key="pre_amp",
        translation_key="pre_amp",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda client: client.state.pre_amp_mode,
        set_value_fn=lambda client, value: client.set_pre_amp_mode(value),
    ),
    CambridgeAudioSwitchEntityDescription(
        key="early_update",
        translation_key="early_update",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda client: client.update.early_update,
        set_value_fn=lambda client, value: client.set_early_update(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CambridgeAudioConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cambridge Audio switch entities based on a config entry."""
    async_add_entities(
        CambridgeAudioSwitch(entry.runtime_data, description)
        for description in CONTROL_ENTITIES
    )


class CambridgeAudioSwitch(CambridgeAudioEntity, SwitchEntity):
    """Defines a Cambridge Audio switch entity."""

    entity_description: CambridgeAudioSwitchEntityDescription

    def __init__(
        self,
        client: StreamMagicClient,
        description: CambridgeAudioSwitchEntityDescription,
    ) -> None:
        """Initialize Cambridge Audio switch."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.info.unit_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.value_fn(self.client)

    @command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_value_fn(self.client, True)

    @command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_value_fn(self.client, False)
