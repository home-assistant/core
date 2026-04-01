"""Support for Cambridge Audio number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiostreammagic import StreamMagicClient

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CambridgeAudioConfigEntry
from .entity import CambridgeAudioEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CambridgeAudioNumberEntityDescription(NumberEntityDescription):
    """Describes Cambridge Audio number entity."""

    exists_fn: Callable[[StreamMagicClient], bool] = lambda _: True
    value_fn: Callable[[StreamMagicClient], int]
    set_value_fn: Callable[[StreamMagicClient, int], Awaitable[None]]


def room_correction_intensity(client: StreamMagicClient) -> int:
    """Get room correction intensity."""
    if TYPE_CHECKING:
        assert client.audio.tilt_eq is not None
    return client.audio.tilt_eq.intensity


CONTROL_ENTITIES: tuple[CambridgeAudioNumberEntityDescription, ...] = (
    CambridgeAudioNumberEntityDescription(
        key="room_correction_intensity",
        translation_key="room_correction_intensity",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-15,
        native_max_value=15,
        native_step=1,
        exists_fn=lambda client: client.audio.tilt_eq is not None,
        value_fn=room_correction_intensity,
        set_value_fn=lambda client, value: client.set_room_correction_intensity(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CambridgeAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cambridge Audio number entities based on a config entry."""
    client = entry.runtime_data
    async_add_entities(
        CambridgeAudioNumber(entry.runtime_data, description)
        for description in CONTROL_ENTITIES
        if description.exists_fn(client)
    )


class CambridgeAudioNumber(CambridgeAudioEntity, NumberEntity):
    """Defines a Cambridge Audio number entity."""

    entity_description: CambridgeAudioNumberEntityDescription

    def __init__(
        self,
        client: StreamMagicClient,
        description: CambridgeAudioNumberEntityDescription,
    ) -> None:
        """Initialize Cambridge Audio number entity."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.info.unit_id}-{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.client)

    @command
    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.set_value_fn(self.client, int(value))
