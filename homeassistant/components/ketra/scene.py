"""Ketra Scene Platform integration."""
import logging

from aioketraapi import ButtonChange, WebsocketV2Notification

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import KetraPlatformBase, KetraPlatformCommon
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Ketra scene platform via config entry."""

    plat_common = hass.data[DOMAIN][entry.unique_id]["common_platform"]
    platform = KetraScenePlatform(async_add_entities, plat_common, _LOGGER)
    await platform.setup_platform()
    _LOGGER.info("Platform init complete")


class KetraScenePlatform(KetraPlatformBase):
    """Ketra Scene Platform helper class."""

    def __init__(
        self, add_entities, platform_common: KetraPlatformCommon, logger: logging.Logger
    ):
        """Initialize the scene platform class."""
        super().__init__(add_entities, platform_common, logger)
        self.button_map = {}

    async def setup_platform(self) -> None:
        """Perform platform setup."""
        self.logger.info("Beginning setup_platform()")
        scenes = []
        keypads = await self.hub.get_keypads()
        for keypad in keypads:
            for button in keypad.buttons:
                scene = KetraScene(button)
                scenes.append(KetraScene(button))
                self.button_map[button.id] = scene
        self.add_entities(scenes)
        self.logger.info(f"{len(scenes)} scenes added")
        self.platform_common.add_platform(self)

    async def reload_platform(self) -> None:
        """Reload the platform after a Design Studio Publish operation."""
        new_scenes = []
        current_scene_ids = []
        keypads = await self.hub.get_keypads()
        for keypad in keypads:
            for button in keypad.buttons:
                current_scene_ids.append(button.id)
                if button.id not in self.button_map:
                    scene = KetraScene(button)
                    new_scenes.append(scene)
                    self.button_map[button.id] = scene
        if len(new_scenes) > 0:
            self.logger.info(f"{len(new_scenes)} new scenes added")
        self.add_entities(new_scenes)
        for button_id in list(self.button_map.keys()):
            if button_id not in current_scene_ids:
                self.logger.info(f"Removing scene id '{button_id}'")
                await self.button_map.pop(button_id).async_remove()

    async def refresh_entity_state(self) -> None:
        """Refresh the state of all entities."""
        keypads = await self.hub.get_keypads()
        for keypad in keypads:
            for button in keypad.buttons:
                if button.id in self.button_map:
                    self.button_map[button.id].update_button(button)

    async def websocket_notification(self, notification_model: WebsocketV2Notification):
        """Handle websocket events (invoked from platform_common)."""
        await super().websocket_notification(notification_model)

        if isinstance(notification_model, ButtonChange):
            button_id = notification_model.contents.button_id
            activated = notification_model.contents.activated
            if button_id in self.button_map:
                _LOGGER.debug(
                    "Scene button '%s' %s",
                    self.button_map[button_id].name,
                    "activated" if activated else "deactivated",
                )
                event_data = {
                    "button_id": button_id,
                    "name": self.button_map[button_id].name,
                    "keypad_name": self.button_map[button_id].keypad_name,
                    "activated": activated,
                }
                _LOGGER.debug(
                    "Firing ketra_button_press event with event data: %s",
                    str(event_data),
                )
                self.platform_common.hass.bus.fire("ketra_button_press", event_data)


class KetraScene(Scene):
    """Representation of a Ketra scene."""

    def __init__(self, button):
        """Initialize the scene entity from the Ketra button object."""
        self._button = button
        self._name = button.scene_name

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {}

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:lightbulb"

    async def async_activate(self, **kwargs) -> None:
        """Activate the scene."""
        await self._button.activate()

    @property
    def keypad_name(self):
        """Return the scene name."""
        return self._button.keypad.name

    def update_button(self, button):
        """Update the button after a websocket reconnection."""
        self._button = button
