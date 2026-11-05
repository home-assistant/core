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

from . import Control4ConfigEntry, get_items_of_category
from .const import (
    CONTROL4_CLOSING,
    CONTROL4_ENTITY_TYPE,
    CONTROL4_FULLY_CLOSED,
    CONTROL4_LEVEL,
    CONTROL4_OPENING,
)
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "blinds_shades"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 covers from a config entry."""
    runtime_data = entry.runtime_data

    coordinator = runtime_data.cover_coordinator

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    entity_list = []
    for item in items_of_category:
        try:
            if item["type"] != CONTROL4_ENTITY_TYPE:
                continue
            item_name = item["name"]
            item_id = item["id"]
            item_parent_id = item["parentId"]
            item_manufacturer = None
            item_device_name = None
            item_model = None

            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item.get("manufacturer")
                    item_device_name = parent_item.get("roomName")
                    item_model = parent_item.get("model")
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        if item_id not in coordinator.data:
            _LOGGER.warning(
                "Couldn't get cover state data for %s (ID: %s), skipping setup",
                item_name,
                item_id,
            )
            continue

        entity_list.append(
            Control4Cover(
                runtime_data,
                coordinator,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
            )
        )

    async_add_entities(entity_list)


class Control4Cover(Control4Entity, CoverEntity):
    """Control4 cover entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "blind"
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._cover_data is not None

    def _create_api_object(self) -> C4Blind:
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one,
        without needing to re-init the entire entity.
        """
        return C4Blind(self.runtime_data.director, self._idx)

    @property
    def _cover_data(self) -> dict[str, Any] | None:
        """Return the cover data from the coordinator."""
        return self.coordinator.data.get(self._idx)

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover (0 closed, 100 open)."""
        data = self._cover_data
        if data is None:
            return None
        level = data.get(CONTROL4_LEVEL)
        if level is None:
            return None
        return int(level)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        data = self._cover_data
        if data is None:
            return None
        if (fully_closed := data.get(CONTROL4_FULLY_CLOSED)) is not None:
            return bool(fully_closed)
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    @property
    @override
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        data = self._cover_data
        if data is None:
            return None
        opening = data.get(CONTROL4_OPENING)
        if opening is None:
            return None
        return bool(opening)

    @property
    @override
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        data = self._cover_data
        if data is None:
            return None
        closing = data.get(CONTROL4_CLOSING)
        if closing is None:
            return None
        return bool(closing)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.open()
        await self.coordinator.async_request_refresh()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.close()
        await self.coordinator.async_request_refresh()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        c4_blind = self._create_api_object()
        await c4_blind.stop()
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        c4_blind = self._create_api_object()
        await c4_blind.set_level_target(kwargs[ATTR_POSITION])
        await self.coordinator.async_request_refresh()
