"""Support for Snoo Select."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from python_snoo.containers import SnooData, SnooDevice, SnooLevels
from python_snoo.exceptions import SnooCommandException
from python_snoo.snoo import Snoo

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SnooConfigEntry
from .entity import SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooSelectEntityDescription(SelectEntityDescription):
    """Describes a Snoo Select."""

    value_fn: Callable[[SnooData], str]
    set_value_fn: Callable[[Snoo, SnooDevice, str], Awaitable[None]]


SELECT_DESCRIPTIONS: list[SnooSelectEntityDescription] = [
    SnooSelectEntityDescription(
        key="intensity",
        translation_key="intensity",
        value_fn=lambda data: data.state_machine.level.name,
        set_value_fn=lambda snoo_api, device, state: snoo_api.set_level(
            device, SnooLevels[state]
        ),
        options=[level.name for level in SnooLevels],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device."""
    coordinators = entry.runtime_data
    async_add_entities(
        SnooSelect(coordinator, description)
        for coordinator in coordinators.values()
        for description in SELECT_DESCRIPTIONS
    )


class SnooSelect(SnooDescriptionEntity, SelectEntity):
    """A sensor using Snoo coordinator."""

    entity_description: SnooSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.entity_description.set_value_fn(
                self.coordinator.snoo, self.device, option
            )
        except SnooCommandException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="select_failed",
                translation_placeholders={"name": str(self.name), "option": option},
            ) from err
