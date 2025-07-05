"""Recorder entity registry helper."""

import logging
from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_has_entity_registry_updated_listeners

from .core import Recorder
from .util import filter_unique_constraint_integrity_error, get_instance, session_scope

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the entity hooks."""

    @callback
    def _async_entity_id_changed(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        instance = get_instance(hass)
        if TYPE_CHECKING:
            assert event.data["action"] == "update" and "old_entity_id" in event.data
        old_entity_id = event.data["old_entity_id"]
        new_entity_id = event.data["entity_id"]
        instance.async_update_statistics_metadata(
            old_entity_id, new_statistic_id=new_entity_id
        )
        instance.async_update_states_metadata(
            old_entity_id, new_entity_id=new_entity_id
        )

    @callback
    def entity_registry_changed_filter(
        event_data: er.EventEntityRegistryUpdatedData,
    ) -> bool:
        """Handle entity_id changed filter."""
        return event_data["action"] == "update" and "old_entity_id" in event_data

    if async_has_entity_registry_updated_listeners(hass):
        raise HomeAssistantError(
            "The recorder entity registry listener must be installed"
            " before async_track_entity_registry_updated_event is called"
        )

    hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        _async_entity_id_changed,
        event_filter=entity_registry_changed_filter,
    )


def update_states_metadata(
    instance: Recorder,
    entity_id: str,
    new_entity_id: str,
) -> None:
    """Update the states metadata table when an entity is renamed."""
    states_meta_manager = instance.states_meta_manager
    if not states_meta_manager.active:
        _LOGGER.warning(
            "Cannot rename entity_id `%s` to `%s` "
            "because the states meta manager is not yet active",
            entity_id,
            new_entity_id,
        )
        return

    with session_scope(
        session=instance.get_session(),
        exception_filter=filter_unique_constraint_integrity_error(instance, "state"),
    ) as session:
        if not states_meta_manager.update_metadata(session, entity_id, new_entity_id):
            _LOGGER.warning(
                "Cannot migrate history for entity_id `%s` to `%s` "
                "because the new entity_id is already in use",
                entity_id,
                new_entity_id,
            )
