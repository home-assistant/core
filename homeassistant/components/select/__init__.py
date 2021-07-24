"""Component to allow selecting an option from a list as platforms."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SELECT_OPTION,
        {vol.Required(ATTR_OPTION): cv.string},
        "async_select_option",
    )
    component.async_register_entity_service(
        SERVICE_SELECT_NEXT,
        {vol.Optional(ATTR_CYCLE, default=True): cv.boolean},
        "async_select_next",
    )
    component.async_register_entity_service(
        SERVICE_SELECT_PREVIOUS,
        {vol.Optional(ATTR_CYCLE, default=True): cv.boolean},
        "async_select_previous",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class SelectEntity(Entity):
    """Representation of a Select entity."""

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
        return self._attr_options

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self._attr_current_option

    @callback
    def select_option(self, option: str) -> None:
        """Change the selected option."""
        raise NotImplementedError()

    @callback
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.hass.async_add_executor_job(self.select_option, option)

    @callback
    @final
    async def async_offset_index(self, offset: int, cycle: bool) -> None:
        """Offset current index."""
        if not self.options:
            return
        if self.current_option:
            current_index = self.options.index(self.current_option)
            new_index = current_index + offset
            if cycle:
                new_index = new_index % len(self.options)
            else:
                new_index = max(0, min(new_index, len(self.options) - 1))
        else:
            new_index = 0
        await self.async_select_option(self.options[new_index])

    @callback
    @final
    async def async_select_next(self, cycle: bool) -> None:
        """Select next option."""
        await self.async_offset_index(1, cycle)

    @callback
    @final
    async def async_select_previous(self, cycle: bool) -> None:
        """Select previous option."""
        await self.async_offset_index(-1, cycle)
