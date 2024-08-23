"""Mammotion button sensor entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionButtonSensorEntityDescription(ButtonEntityDescription):
    """Describes Mammotion button sensor entity."""

    press_fn: Callable[[MammotionDataUpdateCoordinator], Awaitable[None]]


BUTTON_SENSORS: tuple[MammotionButtonSensorEntityDescription, ...] = (
    MammotionButtonSensorEntityDescription(
        key="start_map_sync",
        press_fn=lambda coordinator: coordinator.async_sync_maps(),
    ),
    MammotionButtonSensorEntityDescription(
        key="resync_rtk_dock",
        press_fn=lambda coordinator: coordinator.async_rtk_dock_location(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion button sensor entity."""
    coordinator = entry.runtime_data

    async_add_entities(
        MammotionButtonSensorEntity(coordinator, entity_description)
        for entity_description in BUTTON_SENSORS
    )


class MammotionButtonSensorEntity(MammotionBaseEntity, ButtonEntity):
    """Mammotion button sensor entity."""

    entity_description: MammotionButtonSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionButtonSensorEntityDescription,
    ) -> None:
        """Initialize the button sensor entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator)
