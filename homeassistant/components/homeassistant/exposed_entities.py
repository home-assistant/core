"""Control which entities are exposed to voice assistants."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import dataclasses
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
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


class ExposedEntities:
    """Control assistant settings."""

    _assistants: dict[str, AssistantPreferences]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._listeners: dict[str, list[Callable[[], None]]] = {}
        self._store: Store[dict[str, dict[str, dict[str, Any]]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def async_initialize(self) -> None:
        """Finish initializing."""
        websocket_api.async_register_command(self._hass, ws_expose_entity)
        websocket_api.async_register_command(self._hass, ws_expose_new_entities_get)
        websocket_api.async_register_command(self._hass, ws_expose_new_entities_set)
        await self.async_load()

    @callback
    def async_listen_entity_updates(
        self, assistant: str, listener: Callable[[], None]
    ) -> None:
        """Listen for updates to entity expose settings."""
        self._listeners.setdefault(assistant, []).append(listener)

    @callback
    def async_expose_entity(
        self, assistant: str, entity_id: str, should_expose: bool
    ) -> None:
        """Expose an entity to an assistant.

        Notify listeners if expose flag was changed.
        """
        entity_registry = er.async_get(self._hass)
        if not (registry_entry := entity_registry.async_get(entity_id)):
            raise HomeAssistantError("Unknown entity")

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
        entity_registry = er.async_get(self._hass)
        result: dict[str, Mapping[str, Any]] = {}

        for entity_id, entry in entity_registry.entities.items():
            if options := entry.options.get(assistant):
                result[entity_id] = options

        return result

    @callback
    def async_get_entity_settings(self, entity_id: str) -> dict[str, Mapping[str, Any]]:
        """Get assistant expose settings for an entity."""
        entity_registry = er.async_get(self._hass)
        result: dict[str, Mapping[str, Any]] = {}

        if not (registry_entry := entity_registry.async_get(entity_id)):
            raise HomeAssistantError("Unknown entity")

        for assistant in KNOWN_ASSISTANTS:
            if options := registry_entry.options.get(assistant):
                result[assistant] = options

        return result

    @callback
    def async_should_expose(self, assistant: str, entity_id: str) -> bool:
        """Return True if an entity should be exposed to an assistant."""
        should_expose: bool

        if entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_registry = er.async_get(self._hass)
        if not (registry_entry := entity_registry.async_get(entity_id)):
            # Entities which are not in the entity registry are not exposed
            return False

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

    def _is_default_exposed(
        self, entity_id: str, registry_entry: er.RegistryEntry
    ) -> bool:
        """Return True if an entity is exposed by default."""
        if (
            registry_entry.entity_category is not None
            or registry_entry.hidden_by is not None
        ):
            return False

        domain = split_entity_id(entity_id)[0]
        if domain in DEFAULT_EXPOSED_DOMAINS:
            return True

        device_class = get_device_class(self._hass, entity_id)
        if (
            domain == "binary_sensor"
            and device_class in DEFAULT_EXPOSED_BINARY_SENSOR_DEVICE_CLASSES
        ):
            return True

        if domain == "sensor" and device_class in DEFAULT_EXPOSED_SENSOR_DEVICE_CLASSES:
            return True

        return False

    async def async_load(self) -> None:
        """Load from the store."""
        data = await self._store.async_load()

        assistants: dict[str, AssistantPreferences] = {}

        if data:
            for domain, preferences in data["assistants"].items():
                assistants[domain] = AssistantPreferences(**preferences)

        self._assistants = assistants

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the preferences."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return data to store in a file."""
        data = {}

        data["assistants"] = {
            domain: preferences.to_json()
            for domain, preferences in self._assistants.items()
        }

        return data


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "homeassistant/expose_entity",
        vol.Required("assistants"): [vol.In(KNOWN_ASSISTANTS)],
        vol.Required("entity_ids"): [str],
        vol.Required("should_expose"): bool,
    }
)
def ws_expose_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Expose an entity to an assistant."""
    entity_registry = er.async_get(hass)
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

    if unknown := next(
        (
            entity_id
            for entity_id in entity_ids
            if entity_id not in entity_registry.entities
        ),
        None,
    ):
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, f"can't expose '{unknown}'"
        )
        return

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    for entity_id in entity_ids:
        for assistant in msg["assistants"]:
            exposed_entities.async_expose_entity(
                assistant, entity_id, msg["should_expose"]
            )
    connection.send_result(msg["id"])


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


@callback
def async_expose_entity(
    hass: HomeAssistant,
    assistant: str,
    entity_id: str,
    should_expose: bool,
) -> None:
    """Get assistant expose settings for an entity."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_expose_entity(assistant, entity_id, should_expose)


@callback
def async_should_expose(hass: HomeAssistant, assistant: str, entity_id: str) -> bool:
    """Return True if an entity should be exposed to an assistant."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    return exposed_entities.async_should_expose(assistant, entity_id)
