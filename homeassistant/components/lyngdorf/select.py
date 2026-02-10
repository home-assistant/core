"""Select platform for Lyngdorf integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lyngdorf.device import Receiver

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LyngdorfSelectEntityDescription(SelectEntityDescription):
    """Describe a Lyngdorf select entity."""

    current_option_fn: Callable[[Receiver], str | None]
    options_fn: Callable[[Receiver], list[str]]
    select_option_fn: Callable[[Receiver, str], None]


def _set_room_perfect(receiver: Receiver, option: str) -> None:
    receiver.room_perfect_position = option


def _set_voicing(receiver: Receiver, option: str) -> None:
    receiver.voicing = option


SELECT_ENTITIES: tuple[LyngdorfSelectEntityDescription, ...] = (
    LyngdorfSelectEntityDescription(
        key="room_perfect_position",
        translation_key="room_perfect_position",
        current_option_fn=lambda r: r.room_perfect_position,
        options_fn=lambda r: r.available_room_perfect_positions or [],
        select_option_fn=_set_room_perfect,
    ),
    LyngdorfSelectEntityDescription(
        key="voicing",
        translation_key="voicing",
        current_option_fn=lambda r: r.voicing,
        options_fn=lambda r: r.available_voicings or [],
        select_option_fn=_set_voicing,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf select entities from a config entry."""
    receiver = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    async_add_entities(
        LyngdorfSelect(receiver, config_entry, device_info, description)
        for description in SELECT_ENTITIES
    )


class LyngdorfSelect(LyngdorfEntity, SelectEntity):
    """Lyngdorf select entity."""

    entity_description: LyngdorfSelectEntityDescription

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(receiver)
        assert config_entry.unique_id
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.current_option_fn(self._receiver)

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return self.entity_description.options_fn(self._receiver)

    def select_option(self, option: str) -> None:
        """Set the selected option."""
        self.entity_description.select_option_fn(self._receiver, option)
