"""The Tag integration."""

from __future__ import annotations

import logging
from typing import Any, final
import uuid

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import websocket_api
from homeassistant.const import CONF_NAME
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_NAME, DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, LOGGER, TAG_ID

_LOGGER = logging.getLogger(__name__)

LAST_SCANNED = "last_scanned"
LAST_SCANNED_BY_DEVICE_ID = "last_scanned_by_device_id"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

TAG_DATA: HassKey[TagStorageCollection] = HassKey(DOMAIN)
SIGNAL_TAG_CHANGED = "signal_tag_changed"

CREATE_FIELDS = {
    vol.Optional(TAG_ID): cv.string,
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
    vol.Optional(DEVICE_ID): cv.string,
}

UPDATE_FIELDS = {
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


class TagStorageCollection(collection.DictStorageCollection):
    """Tag collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    def __init__(
        self,
        store: Store,
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
        # make last_scanned JSON serializeable
        if LAST_SCANNED in data:
            data[LAST_SCANNED] = data[LAST_SCANNED].isoformat()

        # Create entity in entity_registry when creating the tag
        # This is done early to store name only once in entity registry
        self.entity_registry.async_get_or_create(
            DOMAIN,
            DOMAIN,
            data[TAG_ID],
            original_name=data.get(CONF_NAME, DEFAULT_NAME),
            suggested_object_id=slugify(data.get(CONF_NAME, DEFAULT_NAME)),
        )
        data.pop(CONF_NAME)
        return data

    @callback
    def _get_suggested_id(self, info: dict[str, str]) -> str:
        """Suggest an ID based on the config."""
        return info[TAG_ID]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        data = {**item, **self.UPDATE_SCHEMA(update_data)}
        # make last_scanned JSON serializeable
        if LAST_SCANNED in update_data:
            data[LAST_SCANNED] = data[LAST_SCANNED].isoformat()
        if name := data.get(CONF_NAME):
            entity_id = self.entity_registry.async_get_entity_id(
                DOMAIN, DOMAIN, data[TAG_ID]
            )
            if entity_id := self.entity_registry.async_get_entity_id(
                DOMAIN, DOMAIN, data[TAG_ID]
            ):
                self.entity_registry.async_update_entity(entity_id, name=name)
            else:
                self.entity_registry.async_get_or_create(
                    DOMAIN,
                    DOMAIN,
                    data[TAG_ID],
                    original_name=data.get(CONF_NAME, DEFAULT_NAME),
                    suggested_object_id=slugify(data.get(CONF_NAME, DEFAULT_NAME)),
                )
            data.pop(CONF_NAME)

        return data


class TagDictStorageCollectionWebsocket(
    collection.StorageCollectionWebsocket[collection.DictStorageCollection]
):
    """Class to expose tag storage collection management over websocket."""

    def __init__(
        self,
        storage_collection: collection.DictStorageCollection,
        api_prefix: str,
        model_name: str,
        create_schema: ConfigType,
        update_schema: ConfigType,
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
        tag_items = self.storage_collection.async_items()
        for item in tag_items:
            if (
                entity_id := self.entity_registry.async_get_entity_id(
                    DOMAIN, DOMAIN, item[TAG_ID]
                )
            ) and (entity := self.entity_registry.async_get(entity_id)):
                item[CONF_NAME] = entity.name or entity.original_name
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Listing tags %s", tag_items)
        connection.send_result(msg["id"], tag_items)

    async def ws_create_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Create a tag item.

        Provides name from entity registry.
        """
        try:
            data = dict(msg)
            data.pop("id")
            data.pop("type")
            item = await self.storage_collection.async_create_item(data)
            if (
                entity_id := self.entity_registry.async_get_entity_id(
                    DOMAIN, DOMAIN, item[TAG_ID]
                )
            ) and (entity := self.entity_registry.async_get(entity_id)):
                item[CONF_NAME] = entity.name or entity.original_name
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Creating tag %s", item)
            connection.send_result(msg["id"], item)
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(
                msg["id"], websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )

    async def ws_update_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Update a tag item.

        Provides the name from entity registry.
        """
        data = dict(msg)
        msg_id = data.pop("id")
        item_id = data.pop(self.item_id_key)
        data.pop("type")

        try:
            item = await self.storage_collection.async_update_item(item_id, data)
            if (
                entity_id := self.entity_registry.async_get_entity_id(
                    DOMAIN, DOMAIN, item[TAG_ID]
                )
            ) and (entity := self.entity_registry.async_get(entity_id)):
                item[CONF_NAME] = entity.name or entity.original_name
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Sending updated tag %s", item)
            connection.send_result(msg_id, item)
        except collection.ItemNotFound:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {item_id}",
            )
        except vol.Invalid as err:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_INVALID_FORMAT,
                humanize_error(data, err),
            )
        except ValueError as err:
            connection.send_error(
                msg_id, websocket_api.const.ERR_INVALID_FORMAT, str(err)
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tag component."""
    component = EntityComponent[TagEntity](LOGGER, DOMAIN, hass)
    id_manager = TagIDManager()
    hass.data[TAG_DATA] = storage_collection = TagStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    await storage_collection.async_load()
    TagDictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    entity_registry = er.async_get(hass)

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
            entity = entity_registry.async_get_or_create(
                DOMAIN, DOMAIN, updated_config[TAG_ID]
            )
            await component.async_add_entities(
                [
                    TagEntity(
                        hass,
                        entity.name or entity.original_name or DEFAULT_NAME,
                        updated_config[TAG_ID],
                        updated_config.get(LAST_SCANNED),
                        updated_config.get(DEVICE_ID),
                    )
                ]
            )

        elif change_type == collection.CHANGE_UPDATED:
            # When tags are changed or updated in storage
            async_dispatcher_send(
                hass,
                SIGNAL_TAG_CHANGED,
                updated_config.get(DEVICE_ID),
                updated_config.get(LAST_SCANNED),
            )

        # Deleted tags
        elif change_type == collection.CHANGE_REMOVED:
            # When tags are removed from storage
            entity_id = entity_registry.async_get_entity_id(
                DOMAIN, DOMAIN, updated_config[TAG_ID]
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

    storage_collection.async_add_listener(tag_change_listener)

    entities: list[TagEntity] = []
    for tag in storage_collection.async_items():
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Adding tag: %s", tag)
        entity_id = entity_registry.async_get_entity_id(DOMAIN, DOMAIN, tag[TAG_ID])
        if entity_id := entity_registry.async_get_entity_id(
            DOMAIN, DOMAIN, tag[TAG_ID]
        ):
            entity = entity_registry.async_get(entity_id)
        else:
            entity = entity_registry.async_get_or_create(
                DOMAIN,
                DOMAIN,
                tag[TAG_ID],
                original_name=tag.get(CONF_NAME, DEFAULT_NAME),
                suggested_object_id=slugify(tag.get(CONF_NAME, DEFAULT_NAME)),
            )
        name = DEFAULT_NAME
        if entity:
            name = entity.name or entity.original_name or name
        entities.append(
            TagEntity(
                hass,
                name,
                tag[TAG_ID],
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
    _attr_translation_key = DOMAIN
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        tag_id: str,
        last_scanned: str | None,
        device_id: str | None,
    ) -> None:
        """Initialize the Tag event."""
        self.hass = hass
        self._attr_name = name
        self._tag_id = tag_id
        self._attr_unique_id = tag_id
        self._last_device_id: str | None = device_id
        self._last_scanned = last_scanned

        self._state_info = {
            "unrecorded_attributes": self._Entity__combined_unrecorded_attributes  # type: ignore[attr-defined]
        }

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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TAG_CHANGED,
                self.async_handle_event,
            )
        )
