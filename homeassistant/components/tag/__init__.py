"""The Tag integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, final
import uuid

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_NAME, DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, LOGGER, TAG_ID

_LOGGER = logging.getLogger(__name__)

LAST_SCANNED = "last_scanned"
LAST_SCANNED_BY_DEVICE_ID = "last_scanned_by_device_id"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 3

TAG_DATA: HassKey[TagStorageCollection] = HassKey(DOMAIN)

CREATE_FIELDS: VolDictType = {
    vol.Optional(TAG_ID): cv.string,
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
    vol.Optional(DEVICE_ID): cv.string,
}

UPDATE_FIELDS: VolDictType = {
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
    vol.Optional(DEVICE_ID): cv.string,
}

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class TagIDExistsError(HomeAssistantError):
    """Raised when an item is not found."""

    def __init__(self, item_id: str) -> None:
        """Initialize tag ID exists error."""
        super().__init__(f"Tag with ID {item_id} already exists.")
        self.item_id = item_id


class TagIDManager(collection.IDManager):
    """ID manager for tags."""

    def generate_id(self, suggestion: str) -> str:
        """Generate an ID."""
        if self.has_id(suggestion):
            raise TagIDExistsError(suggestion)

        return suggestion


def _create_entry(
    entity_registry: er.EntityRegistry, tag_id: str, name: str | None
) -> er.RegistryEntry:
    """Create an entity registry entry for a tag."""
    entry = entity_registry.async_get_or_create(
        DOMAIN,
        DOMAIN,
        tag_id,
        original_name=f"{DEFAULT_NAME} {tag_id}",
        suggested_object_id=slugify(name) if name else tag_id,
    )
    if name:
        return entity_registry.async_update_entity(entry.entity_id, name=name)
    return entry


class TagStore(Store[collection.SerializedStorageCollection]):
    """Store tag data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> dict:
        """Migrate to the new version."""
        data = old_data
        if old_major_version == 1 and old_minor_version < 2:
            entity_registry = er.async_get(self.hass)
            # Version 1.2 moves name to entity registry
            for tag in data["items"]:
                # Copy name in tag store to the entity registry
                _create_entry(entity_registry, tag[CONF_ID], tag.get(CONF_NAME))
        if old_major_version == 1 and old_minor_version < 3:
            # Version 1.3 removes tag_id from the store
            for tag in data["items"]:
                if TAG_ID not in tag:
                    continue
                del tag[TAG_ID]

        if old_major_version > 1:
            raise NotImplementedError

        return data


class TagStorageCollection(collection.DictStorageCollection):
    """Tag collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    def __init__(
        self,
        store: TagStore,
        id_manager: collection.IDManager | None = None,
    ) -> None:
        """Initialize the storage collection."""
        super().__init__(store, id_manager)
        self.entity_registry = er.async_get(self.hass)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)
        if not data[TAG_ID]:
            data[TAG_ID] = str(uuid.uuid4())
        # Move tag id to id
        data[CONF_ID] = data.pop(TAG_ID)
        # make last_scanned JSON serializeable
        if LAST_SCANNED in data:
            data[LAST_SCANNED] = data[LAST_SCANNED].isoformat()

        # Create entity in entity_registry when creating the tag
        # This is done early to store name only once in entity registry
        _create_entry(self.entity_registry, data[CONF_ID], data.get(CONF_NAME))
        return data

    @callback
    def _get_suggested_id(self, info: dict[str, str]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_ID]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        data = {**item, **self.UPDATE_SCHEMA(update_data)}
        tag_id = item[CONF_ID]
        # make last_scanned JSON serializeable
        if LAST_SCANNED in update_data:
            data[LAST_SCANNED] = data[LAST_SCANNED].isoformat()
        if name := data.get(CONF_NAME):
            if entity_id := self.entity_registry.async_get_entity_id(
                DOMAIN, DOMAIN, tag_id
            ):
                self.entity_registry.async_update_entity(entity_id, name=name)
            else:
                raise collection.ItemNotFound(tag_id)

        return data

    def _serialize_item(self, item_id: str, item: dict) -> dict:
        """Return the serialized representation of an item for storing.

        We don't store the name, it's stored in the entity registry.
        """
        return {k: v for k, v in item.items() if k != CONF_NAME}


class TagDictStorageCollectionWebsocket(
    collection.StorageCollectionWebsocket[TagStorageCollection]
):
    """Class to expose tag storage collection management over websocket."""

    def __init__(
        self,
        storage_collection: TagStorageCollection,
        api_prefix: str,
        model_name: str,
        create_schema: VolDictType,
        update_schema: VolDictType,
    ) -> None:
        """Initialize a websocket for tag."""
        super().__init__(
            storage_collection, api_prefix, model_name, create_schema, update_schema
        )
        self.entity_registry = er.async_get(storage_collection.hass)

    @callback
    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items specifically for tag.

        Provides name from entity_registry instead of storage collection.
        """
        tag_items = []
        for item in self.storage_collection.async_items():
            # Make a copy to avoid adding name to the stored entry
            item = {k: v for k, v in item.items() if k != "migrated"}
            if (
                entity_id := self.entity_registry.async_get_entity_id(
                    DOMAIN, DOMAIN, item[CONF_ID]
                )
            ) and (entity := self.entity_registry.async_get(entity_id)):
                item[CONF_NAME] = entity.name or entity.original_name
            tag_items.append(item)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Listing tags %s", tag_items)
        connection.send_result(msg["id"], tag_items)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tag component."""
    component = EntityComponent[TagEntity](LOGGER, DOMAIN, hass)
    id_manager = TagIDManager()
    hass.data[TAG_DATA] = storage_collection = TagStorageCollection(
        TagStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        ),
        id_manager,
    )
    await storage_collection.async_load()
    TagDictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    entity_registry = er.async_get(hass)
    entity_update_handlers: dict[str, Callable[[str | None, str | None], None]] = {}

    async def tag_change_listener(
        change_type: str, item_id: str, updated_config: dict
    ) -> None:
        """Tag storage change listener."""

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s, item: %s, update: %s", change_type, item_id, updated_config
            )
        if change_type == collection.CHANGE_ADDED:
            # When tags are added to storage
            entity = _create_entry(entity_registry, updated_config[CONF_ID], None)
            if TYPE_CHECKING:
                assert entity.original_name
            await component.async_add_entities(
                [
                    TagEntity(
                        entity_update_handlers,
                        entity.name or entity.original_name,
                        updated_config[CONF_ID],
                        updated_config.get(LAST_SCANNED),
                        updated_config.get(DEVICE_ID),
                    )
                ]
            )

        elif change_type == collection.CHANGE_UPDATED:
            # When tags are changed or updated in storage
            if handler := entity_update_handlers.get(updated_config[CONF_ID]):
                handler(
                    updated_config.get(DEVICE_ID),
                    updated_config.get(LAST_SCANNED),
                )

        # Deleted tags
        elif change_type == collection.CHANGE_REMOVED:
            # When tags are removed from storage
            entity_id = entity_registry.async_get_entity_id(
                DOMAIN, DOMAIN, updated_config[CONF_ID]
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

    storage_collection.async_add_listener(tag_change_listener)

    entities: list[TagEntity] = []
    for tag in storage_collection.async_items():
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Adding tag: %s", tag)
        entity_id = entity_registry.async_get_entity_id(DOMAIN, DOMAIN, tag[CONF_ID])
        if entity_id := entity_registry.async_get_entity_id(
            DOMAIN, DOMAIN, tag[CONF_ID]
        ):
            entity = entity_registry.async_get(entity_id)
        else:
            entity = _create_entry(entity_registry, tag[CONF_ID], None)
        if TYPE_CHECKING:
            assert entity
            assert entity.original_name
        name = entity.name or entity.original_name
        entities.append(
            TagEntity(
                entity_update_handlers,
                name,
                tag[CONF_ID],
                tag.get(LAST_SCANNED),
                tag.get(DEVICE_ID),
            )
        )
    await component.async_add_entities(entities)

    return True


async def async_scan_tag(
    hass: HomeAssistant,
    tag_id: str,
    device_id: str | None,
    context: Context | None = None,
) -> None:
    """Handle when a tag is scanned."""
    if DOMAIN not in hass.config.components:
        raise HomeAssistantError("tag component has not been set up.")

    storage_collection = hass.data[TAG_DATA]
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(DOMAIN, DOMAIN, tag_id)

    # Get name from entity registry, default value None if not present
    tag_name = None
    if entity_id and (entity := entity_registry.async_get(entity_id)):
        tag_name = entity.name or entity.original_name

    hass.bus.async_fire(
        EVENT_TAG_SCANNED,
        {TAG_ID: tag_id, CONF_NAME: tag_name, DEVICE_ID: device_id},
        context=context,
    )

    extra_kwargs = {}
    if device_id:
        extra_kwargs[DEVICE_ID] = device_id
    if tag_id in storage_collection.data:
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Updating tag %s with extra %s", tag_id, extra_kwargs)
        await storage_collection.async_update_item(
            tag_id, {LAST_SCANNED: dt_util.utcnow(), **extra_kwargs}
        )
    else:
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Creating tag %s with extra %s", tag_id, extra_kwargs)
        await storage_collection.async_create_item(
            {TAG_ID: tag_id, LAST_SCANNED: dt_util.utcnow(), **extra_kwargs}
        )
    _LOGGER.debug("Tag: %s scanned by device: %s", tag_id, device_id)


class TagEntity(Entity):
    """Representation of a Tag entity."""

    _unrecorded_attributes = frozenset({TAG_ID})
    _attr_should_poll = False

    def __init__(
        self,
        entity_update_handlers: dict[str, Callable[[str | None, str | None], None]],
        name: str,
        tag_id: str,
        last_scanned: str | None,
        device_id: str | None,
    ) -> None:
        """Initialize the Tag event."""
        self._entity_update_handlers = entity_update_handlers
        self._attr_name = name
        self._tag_id = tag_id
        self._attr_unique_id = tag_id
        self._last_device_id: str | None = device_id
        self._last_scanned = last_scanned

    @callback
    def async_handle_event(
        self, device_id: str | None, last_scanned: str | None
    ) -> None:
        """Handle the Tag scan event."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Tag %s scanned by device %s at %s, last scanned at %s",
                self._tag_id,
                device_id,
                last_scanned,
                self._last_scanned,
            )
        self._last_device_id = device_id
        self._last_scanned = last_scanned
        self.async_write_ha_state()

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (
            not self._last_scanned
            or (last_scanned := dt_util.parse_datetime(self._last_scanned)) is None
        ):
            return None
        return last_scanned.isoformat(timespec="milliseconds")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sun."""
        return {TAG_ID: self._tag_id, LAST_SCANNED_BY_DEVICE_ID: self._last_device_id}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._entity_update_handlers[self._tag_id] = self.async_handle_event

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity being removed."""
        await super().async_will_remove_from_hass()
        del self._entity_update_handlers[self._tag_id]
