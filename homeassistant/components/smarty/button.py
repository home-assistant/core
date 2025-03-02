"""Platform to control a Salda Smarty XP/XV ventilation unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pysmarty2 import Smarty

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmartyConfigEntry, SmartyCoordinator
from .entity import SmartyEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmartyButtonDescription(ButtonEntityDescription):
    """Class describing Smarty button."""

    press_fn: Callable[[Smarty], bool | None]


ENTITIES: tuple[SmartyButtonDescription, ...] = (
    SmartyButtonDescription(
        key="reset_filters_timer",
        translation_key="reset_filters_timer",
        press_fn=lambda smarty: smarty.reset_filters_timer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarty Button Platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        SmartyButton(coordinator, description) for description in ENTITIES
    )


class SmartyButton(SmartyEntity, ButtonEntity):
    """Representation of a Smarty Button."""

    entity_description: SmartyButtonDescription

    def __init__(
        self,
        coordinator: SmartyCoordinator,
        entity_description: SmartyButtonDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(
            self.entity_description.press_fn, self.coordinator.client
        )
        await self.coordinator.async_refresh()
