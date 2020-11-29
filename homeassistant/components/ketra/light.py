"""Ketra Light Platform integration."""
import logging

from aioketraapi import GroupStateChange, LampState, WebsocketV2Notification

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

from . import KetraPlatformBase, KetraPlatformCommon
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Ketra light platform via config entry."""

    plat_common = hass.data[DOMAIN][entry.unique_id]["common_platform"]
    platform = KetraLightPlatform(async_add_entities, plat_common, _LOGGER)
    await platform.setup_platform()
    _LOGGER.info("Platform init complete")


class KetraLightPlatform(KetraPlatformBase):
    """Ketra Light Platform helper class."""

    def __init__(
        self, add_entities, platform_common: KetraPlatformCommon, logger: logging.Logger
    ):
        """Initialize the light platform class."""
        super().__init__(add_entities, platform_common, logger)
        self.group_map = {}

    async def setup_platform(self) -> None:
        """Perform platform setup."""
        self.logger.info("Beginning setup_platform()")
        groups = []
        for group in await self.hub.get_groups():
            group_entity = KetraGroup(group)
            groups.append(group_entity)
            self.group_map[group.id] = group_entity
        self.add_entities(groups)
        self.logger.info(f"{len(groups)} light groups added")
        self.platform_common.add_platform(self)

    async def reload_platform(self) -> None:
        """Reload the platform after a Design Studio Publish operation."""
        new_groups = []
        current_groups = await self.hub.get_groups()
        current_groups_ids = []
        for group in current_groups:
            current_groups_ids.append(group.id)
            if group.id not in self.group_map:
                group_entity = KetraGroup(group)
                new_groups.append(group_entity)
                self.group_map[group.id] = group_entity
        if len(new_groups) > 0:
            self.logger.info(f"{len(new_groups)} new lights added")
        self.add_entities(new_groups)
        for group_id in list(self.group_map.keys()):
            if group_id not in current_groups_ids:
                self.logger.info(f"Removing group id '{group_id}'")
                await self.group_map.pop(group_id).async_remove()

    async def refresh_entity_state(self) -> None:
        """Refresh the state of all entities."""
        self.logger.info("Refreshing state of all light entities")
        all_groups = await self.hub.get_groups()
        for group in all_groups:
            if group.id in self.group_map:
                self.group_map[group.id].update_state(group)

    async def websocket_notification(self, notification_model: WebsocketV2Notification):
        """Handle websocket events (invoked from platform_common)."""
        await super().websocket_notification(notification_model)

        if isinstance(notification_model, GroupStateChange):
            changed_groups = notification_model.group_ids
            if len(changed_groups) > 4:
                # get all groups in one shot instead of one at a time
                all_groups = await self.hub.get_groups()
                group_names = [group.name for group in all_groups]
                self.logger.debug(f"Groups {' & '.join(group_names)} changed")
                for group in all_groups:
                    if group.id in self.group_map and group.id in changed_groups:
                        self.group_map[group.id].update_state(group)
            else:
                for group_id in changed_groups:
                    if group_id in self.group_map:
                        self.logger.debug(
                            f"Group {self.group_map[group_id].name} changed"
                        )
                        self.group_map[group_id].update_state()


class KetraGroup(LightEntity):
    """Representation of a Ketra Light Group as a Hass Light Entity."""

    def __init__(self, group):
        """Initialize the light entity from the Ketra Group object."""
        self._supported_features = (
            SUPPORT_BRIGHTNESS
            | SUPPORT_COLOR
            | SUPPORT_COLOR_TEMP
            | SUPPORT_TRANSITION
            | SUPPORT_WHITE_VALUE
        )
        self._group = group
        self._lamp_state = group.state

    def update_state(self, updated_group=None):
        """
        Update the state of the entity.

        Called by KetraLightPlatform in response to a websocket callback indicating a change to a light group.
        Adopts the state of updated_group if it is provided, and calls schedule_update_ha_state to trigger
        an entity state update, with force_refresh=True only if updated_group is None.
        """
        if updated_group is not None:
            self._group = updated_group
            self._lamp_state = self._group.state
        self.schedule_update_ha_state(force_refresh=(updated_group is None))

    @property
    def should_poll(self):
        """
        Return whether hass should poll the state of the entity.

        The state will updated through the websocket connection to the hub, thus polling is disabled.
        """
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
        return self._group.name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if not self.is_on:
            return None
        return self._lamp_state.brightness * 255

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        cct = self._lamp_state.cct
        if cct == 0 or cct is None:
            return None
        return 1000000 / cct

    @property
    def state_attributes(self):
        """Return state attributes."""
        if not self.is_on:
            return None

        data = {}
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
        """
        Return the white value of this light between 0..255.

        This corresponds inversely to the Ketra Vibrancy property which is in the range from 0..1.
        """
        vibrancy = self._lamp_state.vibrancy
        white_level = 1.0 - vibrancy
        return white_level * 255

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._lamp_state.power_on

    async def __async_set_lamp_state(self, power_state: bool, **kwargs):
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
        self._lamp_state = self._group.state
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        await self.__async_set_lamp_state(True, **kwargs)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.__async_set_lamp_state(False, **kwargs)

    async def async_update(self):
        """Fetch new state data for this light."""
        await self._group.update_state()
        self._lamp_state = self._group.state
