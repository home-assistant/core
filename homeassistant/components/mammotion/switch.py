from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionSwitchEntityDescription(SwitchEntityDescription):
    """Describes Mammotion switch entity."""

    key: str
    set_fn: Callable[[MammotionDataUpdateCoordinator, bool], Awaitable[None]]


YUKA_SWITCH_ENTITIES: tuple[MammotionSwitchEntityDescription, ...] = (
    MammotionSwitchEntityDescription(
        key="mowing_on_off",
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: print(f"Mowing {'on' if value else 'off'}"),
    ),
    MammotionSwitchEntityDescription(
        key="dump_grass_on_off",
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: print(
            f"Dump grass {'on' if value else 'off'}"
        ),
    ),
)

SWITCH_ENTITIES: tuple[MammotionSwitchEntityDescription, ...] = (
    MammotionSwitchEntityDescription(
        key="blades_on_off",
        set_fn=lambda coordinator, value: coordinator.async_start_stop_blades(value),
    ),
    MammotionSwitchEntityDescription(
        key="rain_detection_on_off",
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: print(
            f"Rain detection {'on' if value else 'off'}"
        ),
    ),
    MammotionSwitchEntityDescription(
        key="side_led_on_off",
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: print(f"Side LED {'on' if value else 'off'}"),
    ),
    MammotionSwitchEntityDescription(
        key="perimeter_first_on_off",
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: print(
            f"perimeter mow first {'on' if value else 'off'}"
        ),
    ),
)


# Example setup usage
async def async_setup_entry(
    hass: HomeAssistant, entry: MammotionConfigEntry, async_add_entities: Callable
) -> None:
    """Set up the Mammotion switch entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        MammotionSwitchEntity(coordinator, entity_description)
        for entity_description in SWITCH_ENTITIES
    )


class MammotionSwitchEntity(MammotionBaseEntity, SwitchEntity):
    entity_description: MammotionSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_is_on = False  # Default state

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        await self.entity_description.set_fn(self.coordinator, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        await self.entity_description.set_fn(self.coordinator, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state."""
