"""Lovelace resources support."""
from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.const import CONF_ID, CONF_RESOURCES, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, storage

from .const import (
    CONF_RESOURCE_TYPE_WS,
    DOMAIN,
    RESOURCE_CREATE_FIELDS,
    RESOURCE_SCHEMA,
    RESOURCE_UPDATE_FIELDS,
)
from .dashboard import LovelaceConfig

RESOURCE_STORAGE_KEY = f"{DOMAIN}_resources"
RESOURCES_STORAGE_VERSION = 1
_LOGGER = logging.getLogger(__name__)


class ResourceYAMLCollection:
    """Collection representing static YAML."""

    loaded = True

    def __init__(self, data):
        """Initialize a resource YAML collection."""
        self.data = data

    async def async_get_info(self):
        """Return the resources info for YAML mode."""
        return {"resources": len(self.async_items() or [])}

    @callback
    def async_items(self) -> list[dict]:
        """Return list of items in collection."""
        return self.data


class ResourceStorageCollection(collection.DictStorageCollection):
    """Collection to store resources."""

    loaded = False
    CREATE_SCHEMA = vol.Schema(RESOURCE_CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(RESOURCE_UPDATE_FIELDS)

    def __init__(self, hass: HomeAssistant, ll_config: LovelaceConfig) -> None:
        """Initialize the storage collection."""
        super().__init__(
            storage.Store(hass, RESOURCES_STORAGE_VERSION, RESOURCE_STORAGE_KEY),
        )
        self.ll_config = ll_config

    async def async_get_info(self):
        """Return the resources info for YAML mode."""
        if not self.loaded:
            await self.async_load()
            self.loaded = True

        return {"resources": len(self.async_items() or [])}

    async def _async_load_data(self) -> collection.SerializedStorageCollection | None:
        """Load the data."""
        if (store_data := await self.store.async_load()) is not None:
            return store_data

        # Import it from config.
        try:
            conf = await self.ll_config.async_load(False)
        except HomeAssistantError:
            return None

        if CONF_RESOURCES not in conf:
            return None

        # Remove it from config and save both resources + config
        resources: list[dict[str, Any]] = conf[CONF_RESOURCES]

        try:
            vol.Schema([RESOURCE_SCHEMA])(resources)
        except vol.Invalid as err:
            _LOGGER.warning("Resource import failed. Data invalid: %s", err)
            return None

        conf.pop(CONF_RESOURCES)

        for item in resources:
            item[CONF_ID] = uuid.uuid4().hex

        data: collection.SerializedStorageCollection = {"items": resources}

        await self.store.async_save(data)
        await self.ll_config.async_save(conf)

        return data

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)
        data[CONF_TYPE] = data.pop(CONF_RESOURCE_TYPE_WS)
        return data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Return unique ID."""
        return uuid.uuid4().hex

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        if not self.loaded:
            await self.async_load()
            self.loaded = True

        update_data = self.UPDATE_SCHEMA(update_data)
        if CONF_RESOURCE_TYPE_WS in update_data:
            update_data[CONF_TYPE] = update_data.pop(CONF_RESOURCE_TYPE_WS)

        return {**item, **update_data}
