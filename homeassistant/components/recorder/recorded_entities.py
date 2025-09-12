"""Control which entities are recorded."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from enum import StrEnum
from itertools import chain
from typing import Any, TypedDict

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .util import get_instance

DATA_RECORDED_ENTITIES: HassKey[RecordedEntities] = HassKey(
    f"{DOMAIN}.recorded_entities"
)

STORAGE_KEY = f"{DOMAIN}.recorded_entities"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 1

SAVE_DELAY = 10


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorded entities."""
    recorded_entities = RecordedEntities(hass)
    await recorded_entities.async_initialize()
    hass.data[DATA_RECORDED_ENTITIES] = recorded_entities


class EntityRecordingDisabler(StrEnum):
    """What disabled recording of an entity."""

    INTEGRATION = "integration"
    USER = "user"


@dataclasses.dataclass(frozen=True)
class RecorderPreferences:
    """Preferences for an assistant."""

    entity_filter_imported: bool

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {"entity_filter_imported": self.entity_filter_imported}


@dataclasses.dataclass(frozen=True)
class RecordedEntity:
    """A recorded entity without a unique_id."""

    recording_disabled_by: EntityRecordingDisabler | None = None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "recording_disabled_by": self.recording_disabled_by,
        }


class SerializedRecordedEntities(TypedDict):
    """Serialized recorded entities storage collection."""

    recorded_entities: dict[str, dict[str, Any]]
    recorder_preferences: dict[str, Any]


class RecordedEntities:
    """Control recording of entities.

    Settings for entities without a unique_id are stored in the store.
    Settings for entities with a unique_id are stored in the entity registry.
    """

    recorder_preferences: RecorderPreferences
    entities: dict[str, RecordedEntity]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._store: Store[SerializedRecordedEntities] = Store(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )

    async def async_initialize(self) -> None:
        """Finish initializing."""
        websocket_api.async_register_command(self._hass, ws_record_entity)
        websocket_api.async_register_command(self._hass, ws_list_recorded_entities)
        await self._async_load_data()

    @callback
    def async_import_entity_filter(
        self, entity_filter: Callable[[str], bool] | None
    ) -> None:
        """Import an entity filter.

        This will disable recording of entities which are filtered out.
        """
        if self.recorder_preferences.entity_filter_imported:
            return

        entity_registry = er.async_get(self._hass)

        # Set entity recording_disabled_by for all entities
        for entity_id in entity_registry.entities:
            self.async_set_entity_option(
                entity_id,
                recording_disabled_by=EntityRecordingDisabler.USER
                if entity_filter and not entity_filter(entity_id)
                else None,
            )
        for entity_id in self._hass.states.async_entity_ids():
            if entity_id in entity_registry.entities:
                continue
            self.async_set_entity_option(
                entity_id,
                recording_disabled_by=EntityRecordingDisabler.USER
                if entity_filter and not entity_filter(entity_id)
                else None,
            )

        self.recorder_preferences = RecorderPreferences(entity_filter_imported=True)
        self._async_schedule_save()

    @callback
    def async_set_entity_option(
        self,
        entity_id: str,
        *,
        recording_disabled_by: EntityRecordingDisabler
        | None
        | UndefinedType = UNDEFINED,
    ) -> None:
        """Set an option."""
        entity_registry = er.async_get(self._hass)
        if not (registry_entry := entity_registry.async_get(entity_id)):
            self._async_set_legacy_entity_option(
                entity_id, recording_disabled_by=recording_disabled_by
            )
            return

        old_recorder_options = registry_entry.options.get(DOMAIN)
        recorder_options = dict(old_recorder_options or {})

        if recording_disabled_by is not UNDEFINED:
            recorder_options["recording_disabled_by"] = recording_disabled_by

        if old_recorder_options == recorder_options:
            return

        entity_registry.async_update_entity_options(entity_id, DOMAIN, recorder_options)

    def _async_set_legacy_entity_option(
        self,
        entity_id: str,
        *,
        recording_disabled_by: EntityRecordingDisabler
        | None
        | UndefinedType = UNDEFINED,
    ) -> None:
        """Set an option."""
        old_recorded_entity = self.entities.get(entity_id)

        changes = {}
        if recording_disabled_by is not UNDEFINED:
            changes["recording_disabled_by"] = recording_disabled_by

        if old_recorded_entity:
            new_recorded_entity = dataclasses.replace(old_recorded_entity, **changes)
        else:
            new_recorded_entity = RecordedEntity(**changes)

        if old_recorded_entity == new_recorded_entity:
            return

        self.entities[entity_id] = new_recorded_entity
        self._async_schedule_save()

    @callback
    def async_get_entity_options(self, entity_id: str) -> RecordedEntity:
        """Get options for an entity."""
        entity_registry = er.async_get(self._hass)

        if registry_entry := entity_registry.async_get(entity_id):
            options: dict[str, Any] = registry_entry.options.get(DOMAIN, {})
            return RecordedEntity(**options)
        if recorded_entity := self.entities.get(entity_id):
            return recorded_entity

        raise HomeAssistantError("Unknown entity")

    @callback
    def async_get_unrecorded_entities(self) -> set[str]:
        """Return a set of entities which should not be recorded."""
        unrecorded_entities = {
            entity_id
            for entity_id, entity in self.entities.items()
            if entity.recording_disabled_by is not None
        }

        entity_registry = er.async_get(self._hass)
        for registry_entry in entity_registry.entities.values():
            if DOMAIN in registry_entry.options:
                if (
                    registry_entry.options[DOMAIN].get("recording_disabled_by")
                    is not None
                ):
                    unrecorded_entities.add(registry_entry.entity_id)

        return unrecorded_entities

    async def _async_load_data(self) -> SerializedRecordedEntities | None:
        """Load from the store."""
        data = await self._store.async_load()

        recorded_entities: dict[str, RecordedEntity] = {}
        recorder_preferences = RecorderPreferences(
            entity_filter_imported=False,
        )

        if data and "recorded_entities" in data:
            for entity_id, preferences in data["recorded_entities"].items():
                recorded_entities[entity_id] = RecordedEntity(
                    recording_disabled_by=preferences["recording_disabled_by"]
                )
        if data and "recorder_preferences" in data:
            recorder_preferences_data = data["recorder_preferences"]
            recorder_preferences = RecorderPreferences(
                entity_filter_imported=recorder_preferences_data.get(
                    "entity_filter_imported", False
                ),
            )

        self.entities = recorded_entities
        self.recorder_preferences = recorder_preferences

        return data

    @callback
    def _async_schedule_save(self) -> None:
        """Notify the recorder and schedule saving the preferences."""
        get_instance(
            self._hass
        ).unrecorded_entities = self.async_get_unrecorded_entities()
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> SerializedRecordedEntities:
        """Return JSON-compatible date for storing to file."""
        return {
            "recorded_entities": {
                entity_id: entity.to_json()
                for entity_id, entity in self.entities.items()
            },
            "recorder_preferences": self.recorder_preferences.to_json(),
        }


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/record_entity/set_options",
        vol.Required("entity_ids"): [str],
        vol.Required("recording_disabled_by"): vol.Any(EntityRecordingDisabler, None),
    }
)
def ws_record_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Set recording options of entities."""
    entity_ids: list[str] = msg["entity_ids"]

    for entity_id in entity_ids:
        async_set_entity_option(
            hass, entity_id, recording_disabled_by=msg["recording_disabled_by"]
        )
    connection.send_result(msg["id"])


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/record_entity/list",
    }
)
def ws_list_recorded_entities(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List entities which have recorder settings."""
    result: dict[str, Any] = {}

    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    entity_registry = er.async_get(hass)
    for entity_id in chain(recorded_entities.entities, entity_registry.entities):
        result[entity_id] = async_get_entity_options(hass, entity_id)
    connection.send_result(msg["id"], {"recorded_entities": result})


@callback
def async_get_entity_options(hass: HomeAssistant, entity_id: str) -> RecordedEntity:
    """Get recorder options for an entity."""
    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    return recorded_entities.async_get_entity_options(entity_id)


@callback
def async_set_entity_option(
    hass: HomeAssistant,
    entity_id: str,
    *,
    recording_disabled_by: EntityRecordingDisabler | None | UndefinedType = UNDEFINED,
) -> None:
    """Set a recorder option for an entity."""
    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    recorded_entities.async_set_entity_option(
        entity_id, recording_disabled_by=recording_disabled_by
    )
