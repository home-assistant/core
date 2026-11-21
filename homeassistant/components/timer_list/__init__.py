"""The Timer list integration.

A timer list entity holds many independent countdown timers (its *items*),
mirroring how a to-do list holds many to-do items. The entity state is the
number of active timers. The platform provides the abstract entity, the shared
data model, and the generic services/websocket API; storing timers and
scheduling their completion is left to concrete implementations, such as the
reusable ``InMemoryTimerListEntity``.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    TimerListEntityFeature,
    TimerListEventType,
    TimerListServices,
    TimerStatus,
)
from .entity import TimerItem, TimerListEntity, TimerListEvent
from .in_memory import InMemoryTimerListEntity
from .services import async_setup_services
from .websocket_api import async_setup as async_setup_websocket_api

__all__ = [
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "InMemoryTimerListEntity",
    "TimerItem",
    "TimerListEntity",
    "TimerListEntityFeature",
    "TimerListEvent",
    "TimerListEventType",
    "TimerListServices",
    "TimerStatus",
    "async_get_timer_list_entity",
]

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


@callback
def entity_became_available(event: Event[EventStateChangedData]) -> bool:
    """Return True if a state change means the entity is newly usable.

    A config entry reload builds a new entity object but leaves its registry
    entry alone, so this transition is the only signal that subscriptions held
    against the old object are now dangling.
    """
    new_state = event.data["new_state"]
    old_state = event.data["old_state"]
    if new_state is None or new_state.state == STATE_UNAVAILABLE:
        return False
    return old_state is None or old_state.state == STATE_UNAVAILABLE


@callback
def async_get_timer_list_entity(
    hass: HomeAssistant, entity_id: str
) -> TimerListEntity | None:
    """Return the timer list entity for an entity ID."""
    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Timer list component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[TimerListEntity](
        _LOGGER, DOMAIN, hass
    )

    async_setup_websocket_api(hass)

    async_setup_services(hass)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)
