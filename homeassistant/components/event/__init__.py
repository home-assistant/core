"""Component for handling incoming events as a platform."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import logging
from typing import Any, Self, final

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_COMPONENT: HassKey[EntityComponent[EventEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


class EventDeviceClass(StrEnum):
    """Device class for events."""

    DOORBELL = "doorbell"
    BUTTON = "button"
    MOTION = "motion"


__all__ = [
    "ATTR_EVENT_TYPE",
    "ATTR_EVENT_TYPES",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "EventDeviceClass",
    "EventEntity",
    "EventEntityDescription",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Event entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[EventEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class EventEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes event entities."""

    device_class: EventDeviceClass | None = None
    event_types: list[str] | None = None


@dataclass
class EventExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    last_event_type: str | None
    last_event_attributes: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored event state from a dict."""
        try:
            return cls(
                restored["last_event_type"],
                restored["last_event_attributes"],
            )
        except KeyError:
            return None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "event_types",
}


class EventEntity(RestoreEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of an Event entity."""

    _entity_component_unrecorded_attributes = frozenset({ATTR_EVENT_TYPES})

    entity_description: EventEntityDescription
    _attr_device_class: EventDeviceClass | None
    _attr_event_types: list[str]
    _attr_state: None

    __last_event_triggered: datetime | None = None
    __last_event_type: str | None = None
    __last_event_attributes: dict[str, Any] | None = None

    @cached_property
    def device_class(self) -> EventDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    def event_types(self) -> list[str]:
        """Return a list of possible events."""
        if hasattr(self, "_attr_event_types"):
            return self._attr_event_types
        if (
            hasattr(self, "entity_description")
            and self.entity_description.event_types is not None
        ):
            return self.entity_description.event_types
        raise AttributeError

    @final
    def _trigger_event(
        self, event_type: str, event_attributes: dict[str, Any] | None = None
    ) -> None:
        """Process a new event."""
        if event_type not in self.event_types:
            raise ValueError(f"Invalid event type {event_type} for {self.entity_id}")
        self.__last_event_triggered = dt_util.utcnow()
        self.__last_event_type = event_type
        self.__last_event_attributes = event_attributes

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
        if (last_event := self.__last_event_triggered) is None:
            return None
        return last_event.isoformat(timespec="milliseconds")

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {ATTR_EVENT_TYPE: self.__last_event_type}
        if last_event_attributes := self.__last_event_attributes:
            attributes |= last_event_attributes
        return attributes

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the event entity is added to hass."""
        await super().async_internal_added_to_hass()
        if (
            (state := await self.async_get_last_state())
            and state.state is not None
            and (event_data := await self.async_get_last_event_data())
        ):
            self.__last_event_triggered = dt_util.parse_datetime(state.state)
            self.__last_event_type = event_data.last_event_type
            self.__last_event_attributes = event_data.last_event_attributes

    @property
    def extra_restore_state_data(self) -> EventExtraStoredData:
        """Return event specific state data to be restored."""
        return EventExtraStoredData(
            self.__last_event_type,
            self.__last_event_attributes,
        )

    async def async_get_last_event_data(self) -> EventExtraStoredData | None:
        """Restore event specific state date."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return EventExtraStoredData.from_dict(restored_last_extra_data.as_dict())
