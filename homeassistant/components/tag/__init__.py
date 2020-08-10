"""The Tag integration."""
import logging
import typing

import voluptuous as vol

from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEVICE_ID = "device_id"
EVENT_TAG_SCANNED = "tag_scanned"
LAST_SCANNED = "last_scanned"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
TAG_ID = "tag_id"
TAGS = "tags"

CREATE_FIELDS = {
    vol.Required(CONF_ID): cv.string,
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional(LAST_SCANNED): cv.datetime,
}


class TagStorageCollection(collection.StorageCollection):
    """Tag collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: typing.Dict) -> typing.Dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: typing.Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_ID]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**data, **update_data}


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tag component."""
    hass.data[DOMAIN] = {}
    id_manager = collection.IDManager()
    hass.data[DOMAIN][TAGS] = storage_collection = TagStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}_storage_collection"),
        id_manager,
    )
    await storage_collection.async_load()
    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)
    return True


@bind_hass
async def async_scan_tag(hass, tag_id, device_id, context=None):
    """Handle when a tag is scanned."""
    hass.bus.async_fire(
        EVENT_TAG_SCANNED, {TAG_ID: tag_id, DEVICE_ID: device_id}, context=context
    )
    helper = hass.data[DOMAIN][TAGS]
    if tag_id in helper.store.data:
        await helper.async_update_item(tag_id, {LAST_SCANNED: dt_util.utcnow()})
    else:
        await helper.async_create_item(
            {CONF_ID: tag_id, LAST_SCANNED: dt_util.utcnow()}
        )
    _LOGGER.debug("Tag: %s scanned by device: %s", tag_id, device_id)
