"""The Tag integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, final
import uuid

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

_LOGGER = logging.getLogger(__name__)

LAST_SCANNED = "last_scanned"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

TAG_DATA: HassKey[TagStorageCollection] = HassKey(DOMAIN)

CREATE_FIELDS = {
    vol.Optional(TAG_ID): cv.string,
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
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

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)
        if not data[TAG_ID]:
            data[TAG_ID] = str(uuid.uuid4())
        # make last_scanned JSON serializeable
        if LAST_SCANNED in data:
            data[LAST_SCANNED] = data[LAST_SCANNED].isoformat()
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
        return data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tag component."""
    id_manager = TagIDManager()
    hass.data[TAG_DATA] = storage_collection = TagStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    await storage_collection.async_load()
    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

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

    # Get name from helper, default value None if not present in data
    tag_name = None
    if tag_data := storage_collection.data.get(tag_id):
        tag_name = tag_data.get(CONF_NAME)

    hass.bus.async_fire(
        EVENT_TAG_SCANNED,
        {TAG_ID: tag_id, CONF_NAME: tag_name, DEVICE_ID: device_id},
        context=context,
    )

    if tag_id in storage_collection.data:
        await storage_collection.async_update_item(
            tag_id, {LAST_SCANNED: dt_util.utcnow()}
        )
    else:
        await storage_collection.async_create_item(
            {TAG_ID: tag_id, LAST_SCANNED: dt_util.utcnow()}
        )
    _LOGGER.debug("Tag: %s scanned by device: %s", tag_id, device_id)


class TagEntity(SensorEntity):
    """Representation of a Tag entity."""

    _entity_component_unrecorded_attributes = frozenset({TAG_ID, DEVICE_ID})

    _attr_state: None

    __last_event_triggered: datetime | None = None
    __last_event_device_id: str | None = None

    def __init__(self, name: str, tag_id: str) -> None:
        """Initialize the Tag entity."""
        self._attr_name = name
        self._tag_id = ""

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.hass.bus.async_listen(EVENT_TAG_SCANNED, self._trigger_tag)
        await super().async_added_to_hass()

    @final
    def _trigger_tag(self, event: Event) -> None:
        """Process a new event."""
        self.__last_event_triggered = event.time_fired.isoformat(
            timespec="milliseconds"
        )
        self.__last_event_device_id = event.data[DEVICE_ID]
        if event_type not in self.event_types:
            raise ValueError(f"Invalid event type {event_type} for {self.entity_id}")
        self.__last_event_triggered = dt_util.utcnow()
        self.__last_event_type = event_type
        self.__last_event_attributes = event_attributes

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (last_event := self.__last_event_triggered) is None:
            return None
        return last_event

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            TAG_ID: self._tag_id,
            DEVICE_ID: self.__last_event_device_id,
        }

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
