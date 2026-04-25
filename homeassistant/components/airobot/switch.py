"""Switch platform for Airobot thermostat."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyairobotrest.exceptions import AirobotError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirobotConfigEntry
from .const import DOMAIN
from .coordinator import AirobotDataUpdateCoordinator
from .entity import AirobotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotSwitchEntityDescription(SwitchEntityDescription):
    """Describes Airobot switch entity."""

    is_on_fn: Callable[[AirobotDataUpdateCoordinator], bool]
    turn_on_fn: Callable[[AirobotDataUpdateCoordinator], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[AirobotDataUpdateCoordinator], Coroutine[Any, Any, None]]


SWITCH_TYPES: tuple[AirobotSwitchEntityDescription, ...] = (
    AirobotSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: (
            coordinator.data.settings.setting_flags.childlock_enabled
        ),
        turn_on_fn=lambda coordinator: coordinator.client.set_child_lock(True),
        turn_off_fn=lambda coordinator: coordinator.client.set_child_lock(False),
    ),
    AirobotSwitchEntityDescription(
        key="actuator_exercise_disabled",
        translation_key="actuator_exercise_disabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=lambda coordinator: (
            coordinator.data.settings.setting_flags.actuator_exercise_disabled
        ),
        turn_on_fn=lambda coordinator: coordinator.client.toggle_actuator_exercise(
            True
        ),
        turn_off_fn=lambda coordinator: coordinator.client.toggle_actuator_exercise(
            False
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot switch entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        AirobotSwitch(coordinator, description) for description in SWITCH_TYPES
    )


class AirobotSwitch(AirobotEntity, SwitchEntity):
    """Representation of an Airobot switch."""

    entity_description: AirobotSwitchEntityDescription

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
        description: AirobotSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator)
        except AirobotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_turn_on_failed",
                translation_placeholders={"switch": self.entity_description.key},
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator)
        except AirobotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_turn_off_failed",
                translation_placeholders={"switch": self.entity_description.key},
            ) from err
        await self.coordinator.async_request_refresh()
