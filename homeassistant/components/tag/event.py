"""The Tag sensor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN, EventEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LAST_SCANNED, TAGS, TagStorageCollection
from .const import DEFAULT_NAME, DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tag Sensor."""
    storage_collection: TagStorageCollection = hass.data[DOMAIN][TAGS]
    entities: dict[str, TagEvent] = {}

    entity_reg = er.async_get(hass)

    async def tag_change_listener(
        change_type: str, item_id: str, updated_config: dict
    ) -> None:
        """Tag event listener."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s, item: %s, update: %s", change_type, item_id, updated_config
            )
        if change_type == collection.CHANGE_ADDED:
            # When tags are added to storage
            entities[updated_config[TAG_ID]] = TagEvent(
                updated_config.get(CONF_NAME, DEFAULT_NAME),
                updated_config[TAG_ID],
                updated_config.get(LAST_SCANNED, ""),
            )
            async_add_entities([entities[updated_config[TAG_ID]]])
        if change_type == collection.CHANGE_UPDATED:
            # When tags are changed or updated in storage
            if entities[updated_config[TAG_ID]]._last_scanned != updated_config.get(  # pylint: disable=protected-access
                LAST_SCANNED, ""
            ):
                entities[updated_config[TAG_ID]].async_handle_event(
                    EVENT_TAG_SCANNED,
                    updated_config.get(DEVICE_ID),
                    updated_config.get(LAST_SCANNED, ""),
                )
        # Deleted tags
        if change_type == collection.CHANGE_REMOVED:
            # When tags is removed from storage
            await entities[updated_config[TAG_ID]].async_remove()
            if entity_id := entity_reg.async_get_entity_id(
                EVENT_DOMAIN, DOMAIN, updated_config[TAG_ID]
            ):
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "Removing entity %s. Tag '%s' with id '%s'",
                        entity_id,
                        updated_config[CONF_NAME],
                        updated_config[TAG_ID],
                    )
                entity_reg.async_remove(entity_id)

    storage_collection.async_add_listener(tag_change_listener)

    for tags in storage_collection.async_items():
        entities[tags[TAG_ID]] = TagEvent(
            tags.get(CONF_NAME, DEFAULT_NAME), tags[TAG_ID], tags.get(LAST_SCANNED, "")
        )

    async_add_entities(entities.values())


class TagEvent(EventEntity):
    """Representation of a Tag event."""

    _unrecorded_attributes = frozenset({TAG_ID})
    _attr_event_types = [EVENT_TAG_SCANNED]

    def __init__(self, name: str, tag_id: str, last_scanned: str) -> None:
        """Initialize the Tag event."""
        self._attr_name = name
        self._tag_id = tag_id
        self._last_device_id: str | None = None
        self._last_scanned = last_scanned
        self._attr_unique_id = tag_id

    @callback
    def async_handle_event(
        self, event: str, device_id: str | None, last_scanned: str
    ) -> None:
        """Handle the Tag scan event."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s for %s with device %s last scanned before %s and scanned now %s",
                event,
                self._tag_id,
                device_id,
                self._last_scanned,
                last_scanned,
            )
        self._last_device_id = device_id
        self._last_scanned = last_scanned
        self._trigger_event(
            event,
            {TAG_ID: self._tag_id, DEVICE_ID: device_id},
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {TAG_ID: self._tag_id, DEVICE_ID: self._last_device_id}
