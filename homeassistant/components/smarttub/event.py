"""Platform for event integration."""

from datetime import datetime
from typing import Any, override

from smarttub import Spa, SpaError

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ATTR_ERRORS
from .controller import SmartTubConfigEntry
from .entity import SmartTubEntity

ATTR_ERROR_CODE = "error_code"
ATTR_ERROR_TITLE = "error_title"
ATTR_ERROR_DESCRIPTION = "error_description"
ATTR_ERROR_TYPE = "error_type"

EVENT_TYPE_ERROR = "error"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartTubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event entities for the spas."""

    controller = entry.runtime_data

    async_add_entities(
        SmartTubErrorEvent(controller.coordinator, spa) for spa in controller.spas
    )


type _ErrorKey = tuple[int, datetime]


def _error_key(error: SpaError) -> _ErrorKey:
    """Return a key identifying an entry in the error history.

    The API provides no identifier for errors.
    """
    return (error.code, error.created_at)


class SmartTubErrorEvent(SmartTubEntity, EventEntity):
    """Fires when the spa reports a new error, or an error is reported again.

    The spa reports its error history. The `active` flag of its entries is not
    reliable, so an entry is considered new when it has not been seen before, or
    reported again when its `updated_at` is newer than previously seen.

    Errors which occurred while Home Assistant was not polling are not reported.
    """

    _attr_event_types = [EVENT_TYPE_ERROR]
    _attr_translation_key = "error"

    def __init__(
        self, coordinator: DataUpdateCoordinator[dict[str, Any]], spa: Spa
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Error event")
        self._seen: dict[_ErrorKey, datetime] = {}

    def _errors(self) -> list[SpaError]:
        """Return the error history from the latest update."""
        return self.coordinator.data[self.spa.id][ATTR_ERRORS]

    @override
    async def async_added_to_hass(self) -> None:
        """Seed the entries already present, so they are not reported as new."""
        await super().async_added_to_hass()
        self._seen = {_error_key(error): error.updated_at for error in self._errors()}

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire an event for each new or updated error."""
        seen: dict[_ErrorKey, datetime] = {}
        for error in sorted(self._errors(), key=lambda error: error.updated_at):
            key = _error_key(error)
            seen[key] = error.updated_at
            if key in self._seen and self._seen[key] >= error.updated_at:
                continue
            self._trigger_event(
                EVENT_TYPE_ERROR,
                {
                    ATTR_ERROR_CODE: error.code,
                    ATTR_ERROR_TITLE: error.title,
                    ATTR_ERROR_DESCRIPTION: error.description,
                    ATTR_ERROR_TYPE: error.error_type,
                },
            )
            self.async_write_ha_state()
        self._seen = seen
        super()._handle_coordinator_update()
