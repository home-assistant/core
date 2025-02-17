"""Button entities for Acaia scales."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from aioacaia.acaiascale import AcaiaScale

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class AcaiaButtonEntityDescription(ButtonEntityDescription):
    """Description for acaia button entities."""

    press_fn: Callable[[AcaiaScale], Coroutine[Any, Any, None]]


BUTTONS: tuple[AcaiaButtonEntityDescription, ...] = (
    AcaiaButtonEntityDescription(
        key="tare",
        translation_key="tare",
        press_fn=lambda scale: scale.tare(),
    ),
    AcaiaButtonEntityDescription(
        key="reset_timer",
        translation_key="reset_timer",
        press_fn=lambda scale: scale.reset_timer(),
    ),
    AcaiaButtonEntityDescription(
        key="start_stop",
        translation_key="start_stop",
        press_fn=lambda scale: scale.start_stop_timer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = entry.runtime_data
    async_add_entities(AcaiaButton(coordinator, description) for description in BUTTONS)


class AcaiaButton(AcaiaEntity, ButtonEntity):
    """Representation of an Acaia button."""

    entity_description: AcaiaButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self._scale)
