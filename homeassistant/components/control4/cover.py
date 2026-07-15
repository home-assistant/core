"""Platform for Control4 Covers (blinds and shades)."""

import logging
from typing import Any, override

from pyControl4.blind import C4Blind

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import get_items_of_category
from .const import CONTROL4_ENTITY_TYPE, Control4ConfigEntry
from .director_utils import director_get_entry_variables
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "blinds_shades"

CONTROL4_LEVEL = "Level"
CONTROL4_FULLY_CLOSED = "Fully Closed"
CONTROL4_OPENING = "Opening"
CONTROL4_CLOSING = "Closing"

_MIN_COVER_LEVEL = 0
_MAX_COVER_LEVEL = 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 covers from a config entry."""
    entry_data = entry.runtime_data
    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)

    entity_list: list[CoverEntity] = []

    for item in items_of_category:
        try:
            if item["type"] != CONTROL4_ENTITY_TYPE:
                continue
            item_name = str(item["name"])
            item_id = item["id"]
            item_area = item.get("roomName")
            item_parent_id = item["parentId"]

            item_manufacturer = None
            item_device_name = None
            item_model = None

            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item.get("manufacturer")
                    item_device_name = parent_item.get("name")
                    item_model = parent_item.get("model")
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        item_attributes = await director_get_entry_variables(hass, entry, item_id)
        if not item_attributes:
            _LOGGER.debug("Skipping cover %s: no initial variables", item_name)
            continue

        entity_list.append(
            Control4Cover(
                entry_data,
                entry,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                item_area,
                item_attributes,
            )
        )

    async_add_entities(entity_list, True)


class Control4Cover(Control4Entity, CoverEntity):
    """Control4 cover (blinds/shades) entity."""

    _attr_translation_key = "blind"
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def _create_blind_api_object(self) -> C4Blind:
        """Create a pyControl4 blind object with the current director token."""
        return C4Blind(self.entry_data.director, self._idx)

    @override
    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position (0-100)."""
        level = self._extra_state_attributes.get(CONTROL4_LEVEL)
        if isinstance(level, str) and level.isdigit():
            level = int(level)
        if isinstance(level, int) and _MIN_COVER_LEVEL <= level <= _MAX_COVER_LEVEL:
            return level
        return None

    @override
    @property
    def is_closed(self) -> bool | None:
        """Return whether cover is closed."""
        if (
            fully_closed := self._extra_state_attributes.get(CONTROL4_FULLY_CLOSED)
        ) is not None:
            return bool(fully_closed)
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    @override
    @property
    def is_closing(self) -> bool | None:
        """Return whether cover is closing."""
        closing = self._extra_state_attributes.get(CONTROL4_CLOSING)
        if closing is None:
            return None
        return bool(closing)

    @override
    @property
    def is_opening(self) -> bool | None:
        """Return whether cover is opening."""
        opening = self._extra_state_attributes.get(CONTROL4_OPENING)
        if opening is None:
            return None
        return bool(opening)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._create_blind_api_object().open()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._create_blind_api_object().close()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._create_blind_api_object().stop()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        await self._create_blind_api_object().set_level_target(
            level=kwargs[ATTR_POSITION]
        )
