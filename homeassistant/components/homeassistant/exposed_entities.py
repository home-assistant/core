"""Control which entities are exposed to voice assistants."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import dataclasses
from itertools import chain
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.collection import (
    IDManager,
    SerializedStorageCollection,
    StorageCollection,
)
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.storage import Store

from .const import DATA_EXPOSED_ENTITIES, DOMAIN

KNOWN_ASSISTANTS = ("cloud.alexa", "cloud.google_assistant", "conversation")

STORAGE_KEY = f"{DOMAIN}.exposed_entities"
STORAGE_VERSION = 1

SAVE_DELAY = 10

DEFAULT_EXPOSED_DOMAINS = {
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "lock",
    "scene",
    "script",
    "switch",
    "vacuum",
    "water_heater",
}

DEFAULT_EXPOSED_BINARY_SENSOR_DEVICE_CLASSES = {
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
    BinarySensorDeviceClass.LOCK,
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.PRESENCE,
    BinarySensorDeviceClass.WINDOW,
}

DEFAULT_EXPOSED_SENSOR_DEVICE_CLASSES = {
    SensorDeviceClass.AQI,
    SensorDeviceClass.CO,
    SensorDeviceClass.CO2,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.PM10,
    SensorDeviceClass.PM25,
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
}

DEFAULT_EXPOSED_ASSISTANT = {
    "conversation": True,
}


@dataclasses.dataclass(frozen=True)
class AssistantPreferences:
    """Preferences for an assistant."""

    expose_new: bool

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {"expose_new": self.expose_new}


@dataclasses.dataclass(frozen=True)
class ExposedEntity:
    """An exposed entity without a unique_id."""

    assistants: dict[str, dict[str, Any]]

    def to_json(self, entity_id: str) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "assistants": self.assistants,
            "id": entity_id,
        }


class SerializedExposedEntities(SerializedStorageCollection):
    """Serialized exposed entities storage storage collection."""

    assistants: dict[str, dict[str, Any]]


class ExposedEntitiesIDManager(IDManager):
    """ID manager for tags."""

    def generate_id(self, suggestion: str) -> str:
        """Generate an ID."""
        assert not self.has_id(suggestion)
        return suggestion


class ExposedEntities(StorageCollection[ExposedEntity, SerializedExposedEntities]):
    """Control assistant settings.

    Settings for entities without a unique_id are stored in the store.
    Settings for entities with a unique_id are stored in the entity registry.
    """

    _assistants: dict[str, AssistantPreferences]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            Store(hass, STORAGE_VERSION, STORAGE_KEY), ExposedEntitiesIDManager()
        )
        self._listeners: dict[str, list[Callable[[], None]]] = {}

    async def async_load(self) -> None:
        """Finish initializing."""
        await super().async_load()
        websocket_api.async_register_command(self.hass, ws_expose_entity)
        websocket_api.async_register_command(self.hass, ws_expose_new_entities_get)
        websocket_api.async_register_command(self.hass, ws_expose_new_entities_set)
        websocket_api.async_register_command(self.hass, ws_list_exposed_entities)

    @callback
    def async_listen_entity_updates(
        self, assistant: str, listener: Callable[[], None]
    ) -> None:
        """Listen for updates to entity expose settings."""
        self._listeners.setdefault(assistant, []).append(listener)

    async def async_expose_entity(
        self, assistant: str, entity_id: str, should_expose: bool
    ) -> None:
        """Expose an entity to an assistant.

        Notify listeners if expose flag was changed.
        """
        entity_registry = er.async_get(self.hass)
        if not (registry_entry := entity_registry.async_get(entity_id)):
            return await self._async_expose_legacy_entity(
                assistant, entity_id, should_expose
            )

        assistant_options: Mapping[str, Any]
        if (
            assistant_options := registry_entry.options.get(assistant, {})
        ) and assistant_options.get("should_expose") == should_expose:
            return

        assistant_options = assistant_options | {"should_expose": should_expose}
        entity_registry.async_update_entity_options(
            entity_id, assistant, assistant_options
        )
        for listener in self._listeners.get(assistant, []):
            listener()

    async def _async_expose_legacy_entity(
        self, assistant: str, entity_id: str, should_expose: bool
    ) -> None:
        """Expose an entity to an assistant.

        Notify listeners if expose flag was changed.
        """
        if (
            (exposed_entity := self.data.get(entity_id))
            and (assistant_options := exposed_entity.assistants.get(assistant, {}))
            and assistant_options.get("should_expose") == should_expose
        ):
            return

        if exposed_entity:
            await self.async_update_item(
                entity_id, {"assistants": {assistant: {"should_expose": should_expose}}}
            )
        else:
            await self.async_create_item(
                {
                    "entity_id": entity_id,
                    "assistants": {assistant: {"should_expose": should_expose}},
                }
            )
        for listener in self._listeners.get(assistant, []):
            listener()

    @callback
    def async_get_expose_new_entities(self, assistant: str) -> bool:
        """Check if new entities are exposed to an assistant."""
        if prefs := self._assistants.get(assistant):
            return prefs.expose_new
        return DEFAULT_EXPOSED_ASSISTANT.get(assistant, False)

    @callback
    def async_set_expose_new_entities(self, assistant: str, expose_new: bool) -> None:
        """Enable an assistant to expose new entities."""
        self._assistants[assistant] = AssistantPreferences(expose_new=expose_new)
        self._async_schedule_save()

    @callback
    def async_get_assistant_settings(
        self, assistant: str
    ) -> dict[str, Mapping[str, Any]]:
        """Get all entity expose settings for an assistant."""
        entity_registry = er.async_get(self.hass)
        result: dict[str, Mapping[str, Any]] = {}

        options: Mapping | None
        for entity_id, exposed_entity in self.data.items():
            if options := exposed_entity.assistants.get(assistant):
                result[entity_id] = options

        for entity_id, entry in entity_registry.entities.items():
            if options := entry.options.get(assistant):
                result[entity_id] = options

        return result

    @callback
    def async_get_entity_settings(self, entity_id: str) -> dict[str, Mapping[str, Any]]:
        """Get assistant expose settings for an entity."""
        entity_registry = er.async_get(self.hass)
        result: dict[str, Mapping[str, Any]] = {}

        assistant_settings: Mapping
        if registry_entry := entity_registry.async_get(entity_id):
            assistant_settings = registry_entry.options
        elif exposed_entity := self.data.get(entity_id):
            assistant_settings = exposed_entity.assistants
        else:
            raise HomeAssistantError("Unknown entity")

        for assistant in KNOWN_ASSISTANTS:
            if options := assistant_settings.get(assistant):
                result[assistant] = options

        return result

    async def async_should_expose(self, assistant: str, entity_id: str) -> bool:
        """Return True if an entity should be exposed to an assistant."""
        should_expose: bool

        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_registry = er.async_get(self.hass)
        if not (registry_entry := entity_registry.async_get(entity_id)):
            return await self._async_should_expose_legacy_entity(assistant, entity_id)
        if assistant in registry_entry.options:
            if "should_expose" in registry_entry.options[assistant]:
                should_expose = registry_entry.options[assistant]["should_expose"]
                return should_expose

        if self.async_get_expose_new_entities(assistant):
            should_expose = self._is_default_exposed(entity_id, registry_entry)
        else:
            should_expose = False

        assistant_options: Mapping[str, Any] = registry_entry.options.get(assistant, {})
        assistant_options = assistant_options | {"should_expose": should_expose}
        entity_registry.async_update_entity_options(
            entity_id, assistant, assistant_options
        )

        return should_expose

    async def _async_should_expose_legacy_entity(
        self, assistant: str, entity_id: str
    ) -> bool:
        """Return True if an entity should be exposed to an assistant."""
        should_expose: bool

        if (
            exposed_entity := self.data.get(entity_id)
        ) and assistant in exposed_entity.assistants:
            if "should_expose" in exposed_entity.assistants[assistant]:
                should_expose = exposed_entity.assistants[assistant]["should_expose"]
                return should_expose

        if self.async_get_expose_new_entities(assistant):
            should_expose = self._is_default_exposed(entity_id, None)
        else:
            should_expose = False

        if exposed_entity:
            await self.async_update_item(
                entity_id, {"assistants": {assistant: {"should_expose": should_expose}}}
            )
        else:
            await self.async_create_item(
                {
                    "entity_id": entity_id,
                    "assistants": {assistant: {"should_expose": should_expose}},
                }
            )

        return should_expose

    def _is_default_exposed(
        self, entity_id: str, registry_entry: er.RegistryEntry | None
    ) -> bool:
        """Return True if an entity is exposed by default."""
        if registry_entry and (
            registry_entry.entity_category is not None
            or registry_entry.hidden_by is not None
        ):
            return False

        domain = split_entity_id(entity_id)[0]
        if domain in DEFAULT_EXPOSED_DOMAINS:
            return True

        device_class = get_device_class(self.hass, entity_id)
        if (
            domain == "binary_sensor"
            and device_class in DEFAULT_EXPOSED_BINARY_SENSOR_DEVICE_CLASSES
        ):
            return True

        if domain == "sensor" and device_class in DEFAULT_EXPOSED_SENSOR_DEVICE_CLASSES:
            return True

        return False

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        entity_id: str = info["entity_id"]
        return entity_id

    async def _update_data(
        self, item: ExposedEntity, update_data: dict
    ) -> ExposedEntity:
        """Return a new updated item."""
        new_assistant_settings: dict[str, Any] = update_data["assistants"]
        old_assistant_settings = item.assistants
        for assistant, old_settings in old_assistant_settings.items():
            new_settings = new_assistant_settings.get(assistant, {})
            new_assistant_settings[assistant] = old_settings | new_settings
        return dataclasses.replace(item, assistants=new_assistant_settings)

    def _create_item(self, item_id: str, data: dict) -> ExposedEntity:
        """Create an item from validated config."""
        del data["entity_id"]
        return ExposedEntity(**data)

    def _deserialize_item(self, data: dict) -> ExposedEntity:
        """Create an item from its serialized representation."""
        del data["entity_id"]
        return ExposedEntity(**data)

    def _serialize_item(self, item_id: str, item: ExposedEntity) -> dict:
        """Return the serialized representation of an item for storing."""
        return item.to_json(item_id)

    async def _async_load_data(self) -> SerializedExposedEntities | None:
        """Load from the store."""
        data = await super()._async_load_data()

        assistants: dict[str, AssistantPreferences] = {}

        if data and "assistants" in data:
            for domain, preferences in data["assistants"].items():
                assistants[domain] = AssistantPreferences(**preferences)

        self._assistants = assistants

        if data and "items" not in data:
            return None  # type: ignore[unreachable]

        return data

    @callback
    def _data_to_save(self) -> SerializedExposedEntities:
        """Return JSON-compatible date for storing to file."""
        base_data = super()._base_data_to_save()
        return {
            "items": base_data["items"],
            "assistants": {
                domain: preferences.to_json()
                for domain, preferences in self._assistants.items()
            },
        }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/expose_entity",
        vol.Required("assistants"): [vol.In(KNOWN_ASSISTANTS)],
        vol.Required("entity_ids"): [str],
        vol.Required("should_expose"): bool,
    }
)
@websocket_api.async_response
async def ws_expose_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Expose an entity to an assistant."""
    entity_ids: str = msg["entity_ids"]

    if blocked := next(
        (
            entity_id
            for entity_id in entity_ids
            if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES
        ),
        None,
    ):
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_ALLOWED, f"can't expose '{blocked}'"
        )
        return

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    for entity_id in entity_ids:
        for assistant in msg["assistants"]:
            await exposed_entities.async_expose_entity(
                assistant, entity_id, msg["should_expose"]
            )
    connection.send_result(msg["id"])


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/expose_entity/list",
    }
)
def ws_list_exposed_entities(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Expose an entity to an assistant."""
    result: dict[str, Any] = {}

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    entity_registry = er.async_get(hass)
    for entity_id in chain(exposed_entities.data, entity_registry.entities):
        result[entity_id] = {}
        entity_settings = async_get_entity_settings(hass, entity_id)
        for assistant, settings in entity_settings.items():
            if "should_expose" not in settings:
                continue
            result[entity_id][assistant] = settings["should_expose"]
    connection.send_result(msg["id"], {"exposed_entities": result})


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/expose_new_entities/get",
        vol.Required("assistant"): vol.In(KNOWN_ASSISTANTS),
    }
)
def ws_expose_new_entities_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Check if new entities are exposed to an assistant."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    expose_new = exposed_entities.async_get_expose_new_entities(msg["assistant"])
    connection.send_result(msg["id"], {"expose_new": expose_new})


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/expose_new_entities/set",
        vol.Required("assistant"): vol.In(KNOWN_ASSISTANTS),
        vol.Required("expose_new"): bool,
    }
)
def ws_expose_new_entities_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Expose new entities to an assistatant."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities(msg["assistant"], msg["expose_new"])
    connection.send_result(msg["id"])


@callback
def async_listen_entity_updates(
    hass: HomeAssistant, assistant: str, listener: Callable[[], None]
) -> None:
    """Listen for updates to entity expose settings."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_listen_entity_updates(assistant, listener)


@callback
def async_get_assistant_settings(
    hass: HomeAssistant, assistant: str
) -> dict[str, Mapping[str, Any]]:
    """Get all entity expose settings for an assistant."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    return exposed_entities.async_get_assistant_settings(assistant)


@callback
def async_get_entity_settings(
    hass: HomeAssistant, entity_id: str
) -> dict[str, Mapping[str, Any]]:
    """Get assistant expose settings for an entity."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    return exposed_entities.async_get_entity_settings(entity_id)


async def async_expose_entity(
    hass: HomeAssistant,
    assistant: str,
    entity_id: str,
    should_expose: bool,
) -> None:
    """Get assistant expose settings for an entity."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    await exposed_entities.async_expose_entity(assistant, entity_id, should_expose)


async def async_should_expose(
    hass: HomeAssistant, assistant: str, entity_id: str
) -> bool:
    """Return True if an entity should be exposed to an assistant."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    return await exposed_entities.async_should_expose(assistant, entity_id)
