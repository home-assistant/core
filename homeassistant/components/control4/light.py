"""Platform for Control4 Lights."""
from __future__ import annotations

import logging

from pyControl4.light import C4Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import Control4Entity, get_items_of_category
from .const import CONF_DIRECTOR, CONTROL4_ENTITY_TYPE, DOMAIN
from .director_utils import director_get_entry_variables

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "lights"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Control4 lights from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)

    entity_list = []

    for item in items_of_category:
        try:
            if item["type"] == CONTROL4_ENTITY_TYPE:
                if item["id"]:
                    item_name = str(item["name"])
                    item_id = item["id"]
                    item_area = item["roomName"]
                    item_parent_id = item["parentId"]

                    item_manufacturer = None
                    item_device_name = None
                    item_model = None

                    for parent_item in items_of_category:
                        if parent_item["id"] == item_parent_id:
                            item_manufacturer = parent_item["manufacturer"]
                            item_device_name = parent_item["name"]
                            item_model = parent_item["model"]
                else:
                    continue
            else:
                continue
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        item_attributes = await director_get_entry_variables(hass, entry, item_id)

        entity_list.append(
            Control4Light(
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


class Control4Light(Control4Entity, LightEntity):
    """Control4 light entity."""

    def create_api_object(self):
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one, without needing to re-init the entire entity.
        """
        return C4Light(self.entry_data[CONF_DIRECTOR], self._idx)

    @property
    def is_on(self):
        """Return whether this light is on or off."""
        if "LIGHT_LEVEL" in self.extra_state_attributes:
            return self.extra_state_attributes["LIGHT_LEVEL"] > 0
        elif "LIGHT_STATE" in self.extra_state_attributes:
            return self.extra_state_attributes["LIGHT_STATE"] > 0
        elif "CURRENT_POWER" in self.extra_state_attributes:
            return self.extra_state_attributes["CURRENT_POWER"] > 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.extra_state_attributes["LIGHT_LEVEL"] * 2.55

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        if self._is_dimmer:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        return 0

    @property
    def _is_dimmer(self):
        if "LIGHT_LEVEL" in self.extra_state_attributes:
            return True
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        c4_light = self.create_api_object()
        if self._is_dimmer:
            if ATTR_TRANSITION in kwargs:
                transition_length = kwargs[ATTR_TRANSITION] * 1000
            else:
                transition_length = 0
            if ATTR_BRIGHTNESS in kwargs:
                brightness = (kwargs[ATTR_BRIGHTNESS] / 255) * 100
            else:
                brightness = 100
            await c4_light.rampToLevel(brightness, transition_length)
        else:
            transition_length = 0
            await c4_light.setLevel(100)
        if transition_length == 0:
            transition_length = 1000
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        c4_light = self.create_api_object()
        if self._is_dimmer:
            if ATTR_TRANSITION in kwargs:
                transition_length = kwargs[ATTR_TRANSITION] * 1000
            else:
                transition_length = 0
            await c4_light.rampToLevel(0, transition_length)
        else:
            transition_length = 0
            await c4_light.setLevel(0)
        if transition_length == 0:
            transition_length = 1500
        await self.async_update_ha_state()
