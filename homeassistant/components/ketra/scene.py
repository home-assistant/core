import logging

from aioketraapi import ButtonChange
from aioketraapi.n4_hub import N4Hub

from homeassistant.components.scene import Scene

from . import KetraPlatform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the scene platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    platform = KetraScenePlatform(
        hass, async_add_entities, discovery_info["hub"], _LOGGER
    )
    await platform.setup_platform()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the Ketra light platform via config entry"""

    hubs = hass.data[DOMAIN][entry.unique_id]["hubs"]
    for hub in hubs:
        platform = KetraScenePlatform(hass, async_add_entities, hub, _LOGGER)
        await platform.setup_platform()
    _LOGGER.info(f"Ketra Scene platform init complete")


class KetraScenePlatform(KetraPlatform):
    def __init__(self, hass, add_entities, hub: N4Hub, logger: logging.Logger):
        super().__init__(hass, add_entities, hub, logger)
        self.button_map = {}

    async def setup_platform(self):
        self.logger.info("KetraScenePlatform setup_platform()")
        scenes = []
        keypads = await self.hub.get_keypads()
        for keypad in keypads:
            for button in keypad.buttons:
                scene = KetraScene(button)
                scenes.append(KetraScene(button))
                self.button_map[button.id] = scene
        self.add_entities(scenes)
        self.logger.info(f"Ketra Scene:  {len(scenes)} scenes added")
        await super().setup_platform()

    async def reload_platform(self):
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
            self.logger.info(f"Ketra Scene: {len(new_scenes)} new scenes added")
        self.add_entities(new_scenes)
        for button_id in list(self.button_map.keys()):
            if button_id not in current_scene_ids:
                self.logger.info(f"Removing scene id '{button_id}'")
                await self.button_map.pop(button_id).async_remove()

    async def websocket_notification(self, notification_model):
        if isinstance(notification_model, ButtonChange):
            button_id = notification_model.contents.button_id
            activated = notification_model.contents.activated
            if button_id in self.button_map:
                _LOGGER.info(
                    f"Ketra Scene:  button {self.button_map[button_id].name} {'activated' if activated else 'deactivated'}!"
                )
                event_data = {
                    "button_id": button_id,
                    "name": self.button_map[button_id].name,
                    "keypad_name": self.button_map[button_id].keypad_name,
                    "activated": activated,
                }
                self.hass.bus.fire("ketra_button_press", event_data)
        await super().websocket_notification(notification_model)


class KetraScene(Scene):
    """Representation of a Ketra scene."""

    def __init__(self, button):
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
        await self._button.activate()

    @property
    def keypad_name(self):
        return self._button.keypad.name
