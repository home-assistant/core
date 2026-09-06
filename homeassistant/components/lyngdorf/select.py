"""Select platform for Lyngdorf integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf import LyngdorfReceiver

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

    current_option_fn: Callable[[LyngdorfReceiver], str | None]
    options_fn: Callable[[LyngdorfReceiver], list[str]]
    # None on the pinned library, a coroutine on 2.x: await whichever it is.
    select_option_fn: Callable[[LyngdorfReceiver, str], Awaitable[None] | None]


SELECT_ENTITIES: tuple[LyngdorfSelectEntityDescription, ...] = (
    LyngdorfSelectEntityDescription(
        key="room_perfect_position",
        translation_key="room_perfect_position",
        current_option_fn=lambda r: r.room_perfect_position,
        options_fn=lambda r: r.room_perfect_positions,
        select_option_fn=lambda r, o: r.set_room_perfect_position(o),
    ),
    LyngdorfSelectEntityDescription(
        key="voicing",
        translation_key="voicing",
        current_option_fn=lambda r: r.voicing,
        options_fn=lambda r: r.voicings,
        select_option_fn=lambda r, o: r.set_voicing(o),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf select entities from a config entry."""
    runtime_data = config_entry.runtime_data

    async_add_entities(
        LyngdorfSelect(
            runtime_data.receiver, config_entry, runtime_data.device_info, description
        )
        for description in SELECT_ENTITIES
    )


class LyngdorfSelect(LyngdorfEntity, SelectEntity):
    """Lyngdorf select entity."""

    entity_description: LyngdorfSelectEntityDescription

    def __init__(
        self,
        receiver: LyngdorfReceiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @override
    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.current_option_fn(self._receiver)

    @override
    @property
    def options(self) -> list[str]:
        """Return available options."""
        return self.entity_description.options_fn(self._receiver)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        result = self.entity_description.select_option_fn(self._receiver, option)
        if result is not None:
            await result
