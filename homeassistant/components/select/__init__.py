"""Component to allow selecting an option from a list as platforms."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, final

from propcache import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

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

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[SelectEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

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
    component = hass.data[DATA_COMPONENT] = EntityComponent[SelectEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SELECT_FIRST,
        None,
        SelectEntity.async_first.__name__,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_LAST,
        None,
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
        SelectEntity.async_handle_select_option.__name__,
    )

    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {vol.Optional(ATTR_CYCLE, default=True): bool},
        SelectEntity.async_previous.__name__,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class SelectEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes select entities."""

    options: list[str] | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "current_option",
    "options",
}


class SelectEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Select entity."""

    _entity_component_unrecorded_attributes = frozenset({ATTR_OPTIONS})

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
        current_option = self.current_option
        if current_option is None or current_option not in self.options:
            return None
        return current_option

    @cached_property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        if hasattr(self, "_attr_options"):
            return self._attr_options
        if (
            hasattr(self, "entity_description")
            and self.entity_description.options is not None
        ):
            return self.entity_description.options
        raise AttributeError

    @cached_property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self._attr_current_option

    @final
    @callback
    def _valid_option_or_raise(self, option: str) -> None:
        """Raise ServiceValidationError on invalid option."""
        options = self.options
        if not options or option not in options:
            friendly_options: str = ", ".join(options or [])
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_valid_option",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "option": option,
                    "options": friendly_options,
                },
            )

    @final
    async def async_handle_select_option(self, option: str) -> None:
        """Service call wrapper to set a new value."""
        self._valid_option_or_raise(option)
        await self.async_select_option(option)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        raise NotImplementedError

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
        current_option = self.current_option
        options = self.options
        if current_option is not None and current_option in self.options:
            current_index = self.options.index(current_option)

        new_index = current_index + offset
        if cycle:
            new_index = new_index % len(options)
        elif new_index < 0:
            new_index = 0
        elif new_index >= len(options):
            new_index = len(options) - 1

        await self.async_select_option(options[new_index])

    @final
    async def _async_select_index(self, idx: int) -> None:
        """Select new option by index."""
        options = self.options
        new_index = idx % len(options)
        await self.async_select_option(options[new_index])
