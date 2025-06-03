"""Platform for Control4 Lights."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from pyControl4.error_handling import C4Exception
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4ConfigEntry, Control4RuntimeData, get_items_of_category
from .const import CONTROL4_ENTITY_TYPE
from .director_utils import update_variables_for_config_entry
from .entity import Control4Entity

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "lights"
CONTROL4_NON_DIMMER_VAR = "LIGHT_STATE"
CONTROL4_DIMMER_VARS = ["LIGHT_LEVEL", "Brightness Percent"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 lights from a config entry."""
    runtime_data = entry.runtime_data
    _LOGGER.debug("Scan interval = %s", runtime_data.scan_interval)

    async def async_update_data_non_dimmer() -> dict[int, dict[str, Any]]:
        """Fetch data from Control4 director for non-dimmer lights."""
        try:
            return await update_variables_for_config_entry(
                hass, entry, {CONTROL4_NON_DIMMER_VAR}
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_update_data_dimmer() -> dict[int, dict[str, Any]]:
        """Fetch data from Control4 director for dimmer lights."""
        try:
            return await update_variables_for_config_entry(
                hass, entry, {*CONTROL4_DIMMER_VARS}
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    non_dimmer_coordinator = DataUpdateCoordinator[dict[int, dict[str, Any]]](
        hass,
        _LOGGER,
        name="light",
        update_method=async_update_data_non_dimmer,
        update_interval=timedelta(seconds=runtime_data.scan_interval),
    )
    dimmer_coordinator = DataUpdateCoordinator[dict[int, dict[str, Any]]](
        hass,
        _LOGGER,
        name="light",
        update_method=async_update_data_dimmer,
        update_interval=timedelta(seconds=runtime_data.scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await non_dimmer_coordinator.async_refresh()
    await dimmer_coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)

    entity_list = []
    for item in items_of_category:
        try:
            if item["type"] == CONTROL4_ENTITY_TYPE:
                item_name = item["name"]
                item_id = item["id"]
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
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s",
                item,
            )
            continue

        if item_id in dimmer_coordinator.data:
            item_is_dimmer = True
            item_coordinator = dimmer_coordinator
        elif item_id in non_dimmer_coordinator.data:
            item_is_dimmer = False
            item_coordinator = non_dimmer_coordinator
        else:
            director = runtime_data.director
            item_variables = await director.getItemVariables(item_id)
            _LOGGER.warning(
                (
                    "Couldn't get light state data for %s, skipping setup. Available"
                    " variables from Control4: %s"
                ),
                item_name,
                item_variables,
            )
            continue

        entity_list.append(
            Control4Light(
                runtime_data,
                item_coordinator,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                item_is_dimmer,
            )
        )

    async_add_entities(entity_list, True)


class Control4Light(Control4Entity, LightEntity):
    """Control4 light entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        runtime_data: Control4RuntimeData,
        coordinator: DataUpdateCoordinator[dict[int, dict[str, Any]]],
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        is_dimmer: bool,
    ) -> None:
        """Initialize Control4 light entity."""
        super().__init__(
            runtime_data,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )
        self._is_dimmer = is_dimmer
        if is_dimmer:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    def _create_api_object(self):
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one, without needing to re-init the entire entity.
        """
        return C4Light(self.runtime_data.director, self._idx)

    @property
    def is_on(self):
        """Return whether this light is on or off."""
        if self._is_dimmer:
            for var in CONTROL4_DIMMER_VARS:
                if var in self.coordinator.data[self._idx]:
                    return self.coordinator.data[self._idx][var] > 0
            raise RuntimeError("Dimmer Variable Not Found")
        return self.coordinator.data[self._idx][CONTROL4_NON_DIMMER_VAR] > 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._is_dimmer:
            for var in CONTROL4_DIMMER_VARS:
                if var in self.coordinator.data[self._idx]:
                    return round(self.coordinator.data[self._idx][var] * 2.55)
        return None

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        if self._is_dimmer:
            return LightEntityFeature.TRANSITION
        return LightEntityFeature(0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        c4_light = self._create_api_object()
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
        delay_time = (transition_length / 1000) + 0.7
        _LOGGER.debug("Delaying light update by %s seconds", delay_time)
        await asyncio.sleep(delay_time)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        c4_light = self._create_api_object()
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
        delay_time = (transition_length / 1000) + 0.7
        _LOGGER.debug("Delaying light update by %s seconds", delay_time)
        await asyncio.sleep(delay_time)
        await self.coordinator.async_request_refresh()
