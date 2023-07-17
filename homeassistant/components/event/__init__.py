"""Component for handling incoming events as a platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, final

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_LOGGER = logging.getLogger(__name__)


class EventDeviceClass(StrEnum):
    """Device class for events."""

    DOORBELL = "doorbell"
    BUTTON = "button"
    MOTION = "motion"


__all__ = [
    "ATTR_EVENT_TYPE",
    "ATTR_EVENT_TYPES",
    "DOMAIN",
    "PLATFORM_SCHEMA_BASE",
    "PLATFORM_SCHEMA",
    "EventDeviceClass",
    "EventEntity",
    "EventEntityDescription",
    "EventEntityFeature",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Event entities."""
    component = hass.data[DOMAIN] = EntityComponent[EventEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[EventEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[EventEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class EventEntityDescription(EntityDescription):
    """A class that describes event entities."""

    device_class: EventDeviceClass | None = None
    event_types: list[str] | None = None


class EventEntity(RestoreEntity):
    """Representation of a Event entity."""

    entity_description: EventEntityDescription
    _attr_device_class: EventDeviceClass | None
    _attr_event_types: list[str]
    _attr_state: None
    _attr_extra_state_attributes: None  # type: ignore[assignment]

    __last_event: datetime | None = None
    __last_event_type: str | None = None
    __last_event_extra_state_attributes: dict[str, Any] | None = None

    @property
    def device_class(self) -> EventDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    def event_types(self) -> list[str]:
        """Return a list of possible events."""
        if hasattr(self, "_attr_event_types"):
            return self._attr_event_types
        if (
            hasattr(self, "entity_description")
            and self.entity_description.event_types is not None
        ):
            return self.entity_description.event_types
        raise AttributeError()

    @final
    @callback
    def async_trigger_event(
        self, event_type: str, extra_state_attributes: dict[str, Any] | None = None
    ) -> None:
        """Process a new event."""
        if event_type not in self.event_types:
            raise ValueError(f"Invalid event type {event_type} for {self.entity_id}")
        self.__last_event = dt_util.utcnow()
        self.__last_event_type = event_type
        self.__last_event_extra_state_attributes = extra_state_attributes
        self.async_write_ha_state()

    @final
    def trigger_event(
        self, event_type: str, extra_state_attributes: dict[str, Any] | None = None
    ) -> None:
        """Process a new event."""
        self.hass.loop.call_soon_threadsafe(
            self.async_trigger_event, event_type, extra_state_attributes
        )

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For events this is True if the entity has a device class.
        """
        return self.device_class is not None

    @property
    @final
    def capability_attributes(self) -> dict[str, list[str]]:
        """Return capability attributes."""
        return {
            ATTR_EVENT_TYPES: self.event_types,
        }

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.__last_event is None:
            return None
        return self.__last_event.isoformat(timespec="milliseconds")

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {ATTR_EVENT_TYPE: self.__last_event_type}

    @property
    @final
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        return self.__last_event_extra_state_attributes

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the event entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state is not None:
            self.__last_event = dt_util.parse_datetime(state.state)

            attributes = dict(state.attributes)
            attributes.pop(ATTR_EVENT_TYPES, None)
            self.__last_event_type = attributes.pop(ATTR_EVENT_TYPE, None)
            self.__last_event_extra_state_attributes = attributes
