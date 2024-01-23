"""Component to allow setting text as platforms."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import StrEnum
import logging
import re
from typing import TYPE_CHECKING, Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_PATTERN,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
)

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "TextEntity", "TextEntityDescription", "TextMode"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Text entities."""
    component = hass.data[DOMAIN] = EntityComponent[TextEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): cv.string},
        _async_set_value,
    )

    return True


async def _async_set_value(entity: TextEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data[ATTR_VALUE]
    if len(value) < entity.min:
        raise ValueError(
            f"Value {value} for {entity.entity_id} is too short (minimum length"
            f" {entity.min})"
        )
    if len(value) > entity.max:
        raise ValueError(
            f"Value {value} for {entity.entity_id} is too long (maximum length {entity.max})"
        )
    if entity.pattern_cmp and not entity.pattern_cmp.match(value):
        raise ValueError(
            f"Value {value} for {entity.entity_id} doesn't match pattern {entity.pattern}"
        )
    await entity.async_set_value(value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[TextEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[TextEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class TextMode(StrEnum):
    """Modes for text entities."""

    PASSWORD = "password"
    TEXT = "text"


class TextEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes text entities."""

    native_min: int = 0
    native_max: int = MAX_LENGTH_STATE_STATE
    mode: TextMode = TextMode.TEXT
    pattern: str | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "mode",
    "native_value",
    "native_min",
    "native_max",
    "pattern",
}


class TextEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Text entity."""

    _entity_component_unrecorded_attributes = frozenset(
        {ATTR_MAX, ATTR_MIN, ATTR_MODE, ATTR_PATTERN}
    )

    entity_description: TextEntityDescription
    _attr_mode: TextMode
    _attr_native_value: str | None
    _attr_native_min: int
    _attr_native_max: int
    _attr_pattern: str | None
    _attr_state: None = None
    __pattern_cmp: re.Pattern | None = None

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_MODE: self.mode,
            ATTR_MIN: self.min,
            ATTR_MAX: self.max,
            ATTR_PATTERN: self.pattern,
        }

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.native_value is None:
            return None
        if len(self.native_value) < self.min:
            raise ValueError(
                f"Entity {self.entity_id} provides state {self.native_value} which is "
                f"too short (minimum length {self.min})"
            )
        if len(self.native_value) > self.max:
            raise ValueError(
                f"Entity {self.entity_id} provides state {self.native_value} which is "
                f"too long (maximum length {self.max})"
            )
        if self.pattern_cmp and not self.pattern_cmp.match(self.native_value):
            raise ValueError(
                f"Entity {self.entity_id} provides state {self.native_value} which "
                f"does not match expected pattern {self.pattern}"
            )
        return self.native_value

    @cached_property
    def mode(self) -> TextMode:
        """Return the mode of the entity."""
        if hasattr(self, "_attr_mode"):
            return self._attr_mode
        if hasattr(self, "entity_description"):
            return self.entity_description.mode
        return TextMode.TEXT

    @cached_property
    def native_min(self) -> int:
        """Return the minimum length of the value."""
        if hasattr(self, "_attr_native_min"):
            return self._attr_native_min
        if hasattr(self, "entity_description"):
            return self.entity_description.native_min
        return 0

    @property
    @final
    def min(self) -> int:
        """Return the minimum length of the value."""
        return max(self.native_min, 0)

    @cached_property
    def native_max(self) -> int:
        """Return the maximum length of the value."""
        if hasattr(self, "_attr_native_max"):
            return self._attr_native_max
        if hasattr(self, "entity_description"):
            return self.entity_description.native_max
        return MAX_LENGTH_STATE_STATE

    @property
    @final
    def max(self) -> int:
        """Return the maximum length of the value."""
        return min(self.native_max, MAX_LENGTH_STATE_STATE)

    @property
    @final
    def pattern_cmp(self) -> re.Pattern | None:
        """Return a compiled pattern."""
        if self.pattern is None:
            self.__pattern_cmp = None
            return None
        if not self.__pattern_cmp or self.pattern != self.__pattern_cmp.pattern:
            self.__pattern_cmp = re.compile(self.pattern)
        return self.__pattern_cmp

    @cached_property
    def pattern(self) -> str | None:
        """Return the regex pattern that the value must match."""
        if hasattr(self, "_attr_pattern"):
            return self._attr_pattern
        if hasattr(self, "entity_description"):
            return self.entity_description.pattern
        return None

    @cached_property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self._attr_native_value

    def set_value(self, value: str) -> None:
        """Change the value."""
        raise NotImplementedError()

    async def async_set_value(self, value: str) -> None:
        """Change the value."""
        await self.hass.async_add_executor_job(self.set_value, value)


@dataclass
class TextExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    native_value: str | None
    native_min: int
    native_max: int

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the text data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> TextExtraStoredData | None:
        """Initialize a stored text state from a dict."""
        try:
            return cls(
                restored["native_value"],
                restored["native_min"],
                restored["native_max"],
            )
        except KeyError:
            return None


class RestoreText(TextEntity, RestoreEntity):
    """Mixin class for restoring previous text state."""

    @property
    def extra_restore_state_data(self) -> TextExtraStoredData:
        """Return text specific state data to be restored."""
        return TextExtraStoredData(
            self.native_value,
            self.native_min,
            self.native_max,
        )

    async def async_get_last_text_data(self) -> TextExtraStoredData | None:
        """Restore attributes."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return TextExtraStoredData.from_dict(restored_last_extra_data.as_dict())
