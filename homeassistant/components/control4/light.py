"""Platform for Control4 Lights."""
from datetime import timedelta
import asyncio
import logging

from pyControl4.light import C4Light
from pyControl4.error_handling import C4Exception

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)

from .const import DOMAIN, UPDATE_INTERVAL
from . import Control4Entity, get_items_of_category

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "lights"
CONTROL4_NON_DIMMER_VAR = "LIGHT_STATE"
CONTROL4_DIMMER_VAR = "LIGHT_LEVEL"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Control4 from a config entry."""
    director = hass.data[DOMAIN][entry.title]["director"]

    async def director_update_data(var: str) -> dict:
        data = await director.getAllItemVariableValue(var)
        return_dict = {}
        for key in data:
            return_dict[key["id"]] = key
        return return_dict

    async def async_update_data_non_dimmer():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            return await director_update_data(CONTROL4_NON_DIMMER_VAR)
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def async_update_data_dimmer():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            return await director_update_data(CONTROL4_DIMMER_VAR)
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    non_dimmer_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="light",
        update_method=async_update_data_non_dimmer,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )
    dimmer_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="light",
        update_method=async_update_data_dimmer,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Fetch initial data so we have data when entities subscribe
    await non_dimmer_coordinator.async_refresh()
    await dimmer_coordinator.async_refresh()

    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)
    for item in items_of_category:
        if item["type"] == 7:
            item_name = item["name"]
            item_id = item["id"]
            item_parent_id = item["parentId"]
            item_is_dimmer = item["capabilities"]["dimmer"]

            if item_is_dimmer:
                item_coordinator = dimmer_coordinator
            else:
                item_coordinator = non_dimmer_coordinator

            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item["manufacturer"]
                    item_device_name = parent_item["name"]
                    item_model = parent_item["model"]
            async_add_entities(
                [
                    Control4Light(
                        hass,
                        entry,
                        item_coordinator,
                        item_name,
                        item_id,
                        item_device_name,
                        item_manufacturer,
                        item_model,
                        item_parent_id,
                        item_is_dimmer,
                    )
                ],
                True,
            )


class Control4Light(Control4Entity, LightEntity):
    """Control4 light entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        name: str,
        idx: int,
        device_name: str,
        device_manufacturer: str,
        device_model: str,
        device_id: int,
        is_dimmer: bool,
    ):
        super().__init__(
            hass,
            entry,
            coordinator,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_id,
        )
        self._is_dimmer = is_dimmer
        # pylint: disable=invalid-name
        self._C4Light = C4Light(self.director, idx)

    @property
    def is_on(self):
        return bool(self._coordinator.data[self._idx]["value"] > 0)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._is_dimmer:
            return self._coordinator.data[self._idx]["value"] * 2.55
        return None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._is_dimmer:
            flags |= SUPPORT_BRIGHTNESS
            flags |= SUPPORT_TRANSITION
        return flags

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        if self._is_dimmer:
            if ATTR_TRANSITION in kwargs:
                transition_length = kwargs[ATTR_TRANSITION] * 1000
            else:
                transition_length = 0
            if ATTR_BRIGHTNESS in kwargs:
                brightness = (kwargs[ATTR_BRIGHTNESS] / 255) * 100
            else:
                brightness = 100
            await self._C4Light.rampToLevel(brightness, transition_length)
        else:
            transition_length = 0
            await self._C4Light.setLevel(100)
        if transition_length == 0:
            transition_length = 1500
        await asyncio.sleep(transition_length / 1000)
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        if self._is_dimmer:
            if ATTR_TRANSITION in kwargs:
                transition_length = kwargs[ATTR_TRANSITION] * 1000
            else:
                transition_length = 0
            await self._C4Light.rampToLevel(0, transition_length)
        else:
            transition_length = 0
            await self._C4Light.setLevel(0)
        if transition_length == 0:
            transition_length = 1500
        await asyncio.sleep(transition_length / 1000)
        await self._coordinator.async_request_refresh()
