"""Component to allow selecting an option from a list as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "ATTR_CYCLE",
    "ATTR_OPTION",
    "ATTR_OPTIONS",
    "DOMAIN",
    "PLATFORM_SCHEMA_BASE",
    "PLATFORM_SCHEMA",
    "SelectEntity",
    "SelectEntityDescription",
    "SERVICE_SELECT_FIRST",
    "SERVICE_SELECT_LAST",
    "SERVICE_SELECT_NEXT",
    "SERVICE_SELECT_OPTION",
    "SERVICE_SELECT_PREVIOUS",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DOMAIN] = EntityComponent[SelectEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SELECT_FIRST,
        {},
        SelectEntity.async_first.__name__,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_LAST,
        {},
        SelectEntity.async_last.__name__,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_NEXT,
        {vol.Optional(ATTR_CYCLE, default=True): bool},
        SelectEntity.async_next.__name__,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_OPTION,
        {vol.Required(ATTR_OPTION): cv.string},
        async_select_option,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {vol.Optional(ATTR_CYCLE, default=True): bool},
        SelectEntity.async_previous.__name__,
    )

    return True


async def async_select_option(entity: SelectEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    option = service_call.data[ATTR_OPTION]
    if option not in entity.options:
        raise ValueError(f"Option {option} not valid for {entity.entity_id}")
    await entity.async_select_option(option)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[SelectEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[SelectEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class SelectEntityDescription(EntityDescription):
    """A class that describes select entities."""

    options: list[str] | None = None


class SelectEntity(Entity):
    """Representation of a Select entity."""

    entity_description: SelectEntityDescription
    _attr_current_option: str | None
    _attr_options: list[str]
    _attr_state: None = None

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_OPTIONS: self.options,
        }

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.current_option is None or self.current_option not in self.options:
            return None
        return self.current_option

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        if hasattr(self, "_attr_options"):
            return self._attr_options
        if (
            hasattr(self, "entity_description")
            and self.entity_description.options is not None
        ):
            return self.entity_description.options
        raise AttributeError()

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self._attr_current_option

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        raise NotImplementedError()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.hass.async_add_executor_job(self.select_option, option)

    @final
    async def async_first(self) -> None:
        """Select first option."""
        await self._async_select_index(0)

    @final
    async def async_last(self) -> None:
        """Select last option."""
        await self._async_select_index(-1)

    @final
    async def async_next(self, cycle: bool) -> None:
        """Select next option.

        If there is no current option, first item is the next.
        """
        if self.current_option is None:
            await self.async_first()
            return
        await self._async_offset_index(1, cycle)

    @final
    async def async_previous(self, cycle: bool) -> None:
        """Select previous option.

        If there is no current option, last item is the previous.
        """
        if self.current_option is None:
            await self.async_last()
            return
        await self._async_offset_index(-1, cycle)

    @final
    async def _async_offset_index(self, offset: int, cycle: bool) -> None:
        """Offset current index."""
        current_index = 0
        if self.current_option is not None and self.current_option in self.options:
            current_index = self.options.index(self.current_option)

        new_index = current_index + offset
        if cycle:
            new_index = new_index % len(self.options)
        elif new_index < 0:
            new_index = 0
        elif new_index >= len(self.options):
            new_index = len(self.options) - 1

        await self.async_select_option(self.options[new_index])

    @final
    async def _async_select_index(self, idx: int) -> None:
        """Select new option by index."""
        new_index = idx % len(self.options)
        await self.async_select_option(self.options[new_index])
