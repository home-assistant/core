"""Platform for Control4 Lights."""

import logging
from typing import Any, override

from pyControl4.light import C4Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import get_items_of_category
from .const import CONTROL4_ENTITY_TYPE, Control4ConfigEntry, Control4RuntimeData
from .director_utils import gather_entry_variables
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "lights"
CONTROL4_BRIGHTNESS_SCALE = (1, 100)

CONTROL4_LIGHT_LEVEL = "LIGHT_LEVEL"
CONTROL4_BRIGHTNESS_PERCENT = "Brightness Percent"
CONTROL4_LIGHT_STATE = "LIGHT_STATE"
CONTROL4_CURRENT_POWER = "CURRENT_POWER"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 lights from a config entry."""
    entry_data = entry.runtime_data
    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)

    pending = []
    for item in items_of_category:
        try:
            if not (
                item["type"] == CONTROL4_ENTITY_TYPE
                and item["id"]
                and item["proxy"] != "fan"
            ):
                continue
            item_name = str(item["name"])
            item_id = item["id"]
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
                "Unknown device properties received from Control4: %s", item
            )
            continue

        pending.append(
            {
                "name": item_name,
                "idx": item_id,
                "device_name": item_device_name,
                "device_manufacturer": item_manufacturer,
                "device_model": item_model,
                "device_parent_id": item_parent_id,
            }
        )

    item_attributes_by_id = await gather_entry_variables(
        hass, entry, [item["idx"] for item in pending]
    )

    entity_list = []
    for item in pending:
        item_attributes = item_attributes_by_id[item["idx"]]
        if not item_attributes:
            _LOGGER.debug("Skipping light %s: no initial variables", item["name"])
            continue

        entity_list.append(
            Control4Light(
                entry_data,
                entry,
                device_attributes=item_attributes,
                **item,
            )
        )

    async_add_entities(entity_list, True)


class Control4Light(Control4Entity, LightEntity):
    """Control4 light entity."""

    _ATTRIBUTES_OF_INTEREST = frozenset(
        {
            CONTROL4_LIGHT_LEVEL,
            CONTROL4_BRIGHTNESS_PERCENT,
            CONTROL4_LIGHT_STATE,
            CONTROL4_CURRENT_POWER,
        }
    )

    def __init__(
        self,
        entry_data: Control4RuntimeData,
        entry: Any,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_parent_id: int,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(
            entry_data,
            entry,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_parent_id,
            device_attributes,
        )
        self._attr_supported_color_modes = (
            {ColorMode.BRIGHTNESS} if self._is_dimmer else {ColorMode.ONOFF}
        )
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if self._is_dimmer else ColorMode.ONOFF
        )

    def create_api_object(self) -> C4Light:
        """Create a pyControl4 device object with the current director token."""
        return C4Light(self.entry_data.director, self._idx)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether this light is on."""
        attrs = self._extra_state_attributes
        for key in (
            CONTROL4_LIGHT_LEVEL,
            CONTROL4_BRIGHTNESS_PERCENT,
            CONTROL4_LIGHT_STATE,
            CONTROL4_CURRENT_POWER,
        ):
            if key in attrs:
                value = self._to_float(attrs[key])
                if value is not None:
                    return value > 0
        return None

    @property
    @override
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        attrs = self._extra_state_attributes
        raw_level = None
        if CONTROL4_LIGHT_LEVEL in attrs:
            raw_level = attrs[CONTROL4_LIGHT_LEVEL]
        elif CONTROL4_BRIGHTNESS_PERCENT in attrs:
            raw_level = attrs[CONTROL4_BRIGHTNESS_PERCENT]
        level = self._to_float(raw_level)
        if level is None:
            return None
        if level <= 0:
            return 0
        level = min(level, 100)
        return value_to_brightness(CONTROL4_BRIGHTNESS_SCALE, level)

    @property
    @override
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        if self._is_dimmer:
            return LightEntityFeature.TRANSITION
        return LightEntityFeature(0)

    @property
    def _is_dimmer(self) -> bool:
        attrs = self._extra_state_attributes
        return CONTROL4_LIGHT_LEVEL in attrs or CONTROL4_BRIGHTNESS_PERCENT in attrs

    def _to_rate_ms(self, transition: float | None) -> int:
        if transition is None:
            return 0
        try:
            return max(0, int(float(transition) * 1000))
        except TypeError, ValueError:
            return 0

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        c4_light = self.create_api_object()
        transition_length = self._to_rate_ms(kwargs.get(ATTR_TRANSITION))
        if self._is_dimmer:
            brightness = (
                round(
                    brightness_to_value(
                        CONTROL4_BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS]
                    )
                )
                if ATTR_BRIGHTNESS in kwargs
                else 100
            )
            await c4_light.ramp_to_level(brightness, transition_length)
        else:
            await c4_light.set_level(100)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        c4_light = self.create_api_object()
        transition_length = self._to_rate_ms(kwargs.get(ATTR_TRANSITION))
        if self._is_dimmer:
            await c4_light.ramp_to_level(0, transition_length)
        else:
            await c4_light.set_level(0)
