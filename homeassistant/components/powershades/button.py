"""PowerShades button platform."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator
from .entity import PowerShadesEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PowerShadesButtonDescription(ButtonEntityDescription):
    """Describes a PowerShades button."""

    press_fn: Callable[[PowerShadesCoordinator], Awaitable[None]]


BUTTONS: tuple[PowerShadesButtonDescription, ...] = (
    PowerShadesButtonDescription(
        key="toggle",
        translation_key="toggle",
        icon="mdi:swap-vertical",
        press_fn=lambda coordinator: coordinator.async_toggle(),
    ),
    PowerShadesButtonDescription(
        key="identify",
        translation_key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda coordinator: coordinator.async_identify(),
    ),
    PowerShadesButtonDescription(
        key="jog_up",
        translation_key="jog_up",
        icon="mdi:chevron-double-up",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_jog_up(),
    ),
    PowerShadesButtonDescription(
        key="jog_down",
        translation_key="jog_down",
        icon="mdi:chevron-double-down",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_jog_down(),
    ),
    PowerShadesButtonDescription(
        key="set_upper_limit",
        translation_key="set_upper_limit",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_set_upper_limit(),
    ),
    PowerShadesButtonDescription(
        key="set_lower_limit",
        translation_key="set_lower_limit",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_set_lower_limit(),
    ),
    PowerShadesButtonDescription(
        key="clear_limits",
        translation_key="clear_limits",
        icon="mdi:eraser",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_clear_limits(),
    ),
    PowerShadesButtonDescription(
        key="step_up",
        translation_key="step_up",
        icon="mdi:arrow-up",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_step_up(),
    ),
    PowerShadesButtonDescription(
        key="step_down",
        translation_key="step_down",
        icon="mdi:arrow-down",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_step_down(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerShadesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PowerShades buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        PowerShadesButton(coordinator, description) for description in BUTTONS
    )


class PowerShadesButton(PowerShadesEntity, ButtonEntity):
    """PowerShades button entity."""

    entity_description: PowerShadesButtonDescription

    def __init__(
        self,
        coordinator: PowerShadesCoordinator,
        description: PowerShadesButtonDescription,
    ) -> None:
        """Initialize the PowerShades button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator)
