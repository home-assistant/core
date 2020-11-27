import logging
from aioketraapi import GroupStateChange, LampState
from aioketraapi.n4_hub import N4Hub
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import KetraPlatform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Ketra light platform via config entry"""

    hubs = hass.data[DOMAIN][entry.unique_id]["hubs"]
    for hub in hubs:
        platform = KetraLightPlatform(hass, async_add_entities, hub, _LOGGER)
        await platform.setup_platform()
    _LOGGER.info(f"Ketra Light platform init complete")


class KetraLightPlatform(KetraPlatform):

    def __init__(self, hass: HomeAssistantType, add_entities, hub: N4Hub, logger: logging.Logger):
        super().__init__(hass, add_entities, hub, logger)
        self.group_map = {}

    async def setup_platform(self):
        self.logger.info("KetraLightPlatform setup_platform()")
        groups = []
        for group in await self.hub.get_groups():
            kg = KetraGroup(group)
            groups.append(kg)
            self.group_map[group.id] = kg
        self.add_entities(groups)
        self.logger.info(f"Ketra Light:  {len(groups)} light groups added")
        await super().setup_platform()

    async def reload_platform(self):
        new_groups = []
        current_groups = await self.hub.get_groups()
        current_groups_ids = []
        for group in current_groups:
            current_groups_ids.append(group.id)
            if group.id not in self.group_map:
                kg = KetraGroup(group)
                new_groups.append(kg)
                self.group_map[group.id] = kg
        if len(new_groups) > 0:
            self.logger.info(f"Ketra Light: {len(new_groups)} new lights added")
        self.add_entities(new_groups)
        for group_id in list(self.group_map.keys()):
            if group_id not in current_groups_ids:
                self.logger.info(f"Removing group id '{group_id}'")
                await self.group_map.pop(group_id).async_remove()

    async def websocket_notification(self, notification_model):
        if isinstance(notification_model, GroupStateChange):
            changed_groups = notification_model.group_ids
            if len(changed_groups) > 4:
                # get all groups
                all_groups = await self.hub.get_groups()
                group_names = [group.name for group in all_groups]
                self.logger.info(
                    f"Ketra Light:  groups {' & '.join(group_names)} changed!"
                )
                for group in all_groups:
                    if group.id in self.group_map and group.id in changed_groups:
                        self.group_map[group.id].update_state(group)
            else:
                for group_id in changed_groups:
                    if group_id in self.group_map:
                        self.logger.info(
                            f"Ketra Light:  group {self.group_map[group_id].name} changed!"
                        )
                        self.group_map[group_id].update_state()

        await super().websocket_notification(notification_model)


class KetraGroup(LightEntity):
    """Representation of a Ketra Light Group"""

    def __init__(self, group):
        """Initialize the light group."""
        self._group = group
        self._name = group.name
        self._supported_features = (
            SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP | SUPPORT_TRANSITION | SUPPORT_WHITE_VALUE
        )
        self._lamp_state = group.state
        self._brightness = self._lamp_state.brightness * 255
        self._state = self.is_on

    def update_state(self, group_model=None):
        if group_model is not None:
            self.update_from_model(group_model)
        self.schedule_update_ha_state(force_refresh=(group_model is None))

    @property
    def should_poll(self):
        """state will updated through the websocket connection to the hub"""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def unique_id(self):
        """Return the unique ID of this light."""
        return self._group.id

    @property
    def device_id(self):
        """Return the ID of this light."""
        return self._group.id

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light. """
        return self._lamp_state.brightness * 255

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        cct = self._lamp_state.cct
        if cct == 0:
            return None
        return 1000000 / cct

    @property
    def state_attributes(self):
        """Return state attributes."""
        if not self.is_on:
            return None

        data = {}
        supported_features = self.supported_features
        data[ATTR_BRIGHTNESS] = self.brightness
        data[ATTR_COLOR_TEMP] = self.color_temp
        data[ATTR_XY_COLOR] = (
            self._lamp_state.x_chromaticity,
            self._lamp_state.y_chromaticity,
        )
        data[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*data[ATTR_XY_COLOR])
        data[ATTR_RGB_COLOR] = color_util.color_xy_to_RGB(*data[ATTR_XY_COLOR])
        data[ATTR_WHITE_VALUE] = self.white_value

        return {key: val for key, val in data.items() if val is not None}

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 1000000 / 10000

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 1000000 / 1100

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        vibrancy = self._lamp_state.vibrancy
        white_level = 1.0 - vibrancy
        return white_level * 255

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._lamp_state.power_on

    async def async_set_lamp_state(self, power_state, **kwargs):
        lamp_state = LampState(power_on=power_state)
        if ATTR_TRANSITION in kwargs:
            lamp_state.transition_time = int(kwargs[ATTR_TRANSITION] * 1000)

        if ATTR_HS_COLOR in kwargs:
            xy_color = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
            lamp_state.x_chromaticity = xy_color[0]
            lamp_state.y_chromaticity = xy_color[1]
        elif ATTR_COLOR_TEMP in kwargs:
            temp = kwargs[ATTR_COLOR_TEMP]
            lamp_state.cct = 1000000 / temp

        if ATTR_BRIGHTNESS in kwargs:
            lamp_state.brightness = kwargs[ATTR_BRIGHTNESS] / 255.0

        if ATTR_WHITE_VALUE in kwargs:
            lamp_state.vibrancy = 1 - (kwargs[ATTR_WHITE_VALUE] / 255.0)

        await self._group.set_state(lamp_state)

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on.
        """
        await self.async_set_lamp_state(True, **kwargs)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.async_set_lamp_state(False, **kwargs)

    async def async_update(self):
        """Fetch new state data for this light.
        """
        await self._group.update_state()
        self._lamp_state = self._group.state

    def update_from_model(self, group_model):
        self._group.update_state_from_model(group_model.state)
