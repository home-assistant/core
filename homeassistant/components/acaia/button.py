"""Button entities for acaia scales."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyacaia_async.acaiascale import AcaiaScale

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity, AcaiaEntityDescription


@dataclass(kw_only=True, frozen=True)
class AcaiaButtonEntityDescription(AcaiaEntityDescription, ButtonEntityDescription):
    """Description for acaia button entities."""

    async_press_fn: Callable[[AcaiaScale], Coroutine[Any, Any, None]]


BUTTONS: tuple[AcaiaButtonEntityDescription, ...] = (
    AcaiaButtonEntityDescription(
        key="tare",
        translation_key="tare",
        async_press_fn=lambda scale: scale.tare(),
    ),
    AcaiaButtonEntityDescription(
        key="reset_timer",
        translation_key="reset_timer",
        async_press_fn=lambda scale: scale.reset_timer(),
    ),
    AcaiaButtonEntityDescription(
        key="start_stop",
        translation_key="start_stop",
        async_press_fn=lambda scale: scale.start_stop_timer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = entry.runtime_data
    async_add_entities(
        [AcaiaButton(coordinator, description) for description in BUTTONS]
    )


class AcaiaButton(AcaiaEntity, ButtonEntity):
    """Representation of a acaia Button."""

    entity_description: AcaiaButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.async_press_fn(self._scale)
        self.async_write_ha_state()
