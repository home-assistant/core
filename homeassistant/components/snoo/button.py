"""Support for Snoo Buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from python_snoo.containers import SnooDevice
from python_snoo.exceptions import SnooCommandException
from python_snoo.snoo import Snoo

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SnooConfigEntry
from .entity import SnooDescriptionEntity


@dataclass(kw_only=True, frozen=True)
class SnooButtonEntityDescription(ButtonEntityDescription):
    """Description for Snoo button entities."""

    press_fn: Callable[[Snoo, SnooDevice], Awaitable[None]]


BUTTON_DESCRIPTIONS: list[SnooButtonEntityDescription] = [
    SnooButtonEntityDescription(
        key="start_snoo",
        translation_key="start_snoo",
        press_fn=lambda snoo, device: snoo.start_snoo(
            device,
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for Snoo device."""
    coordinators = entry.runtime_data
    async_add_entities(
        SnooButton(coordinator, description)
        for coordinator in coordinators.values()
        for description in BUTTON_DESCRIPTIONS
    )


class SnooButton(SnooDescriptionEntity, ButtonEntity):
    """Representation of a Snoo button."""

    entity_description: SnooButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_fn(
                self.coordinator.snoo,
                self.coordinator.device,
            )
        except SnooCommandException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"{self.entity_description.key}_failed",
                translation_placeholders={"name": str(self.name)},
            ) from err
