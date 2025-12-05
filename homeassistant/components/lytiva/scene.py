"""Lytiva Scene platform."""
from __future__ import annotations
import logging
import json
from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Lytiva scenes from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    mqtt = data["mqtt_client"]
    
    scenes: dict[str, LytivaScene] = {}
    
    def on_discovery(payload):
        """Handle scene discovery."""
        try:
            name = payload.get("name")
            unique_id = str(payload.get("unique_id"))
            command_topic = payload.get("command_topic")
            state_topic = payload.get("state_topic")
            payload_on = payload.get("payload_on")
            suggested_area = payload.get("suggested_area")
            device_info = payload.get("device")
            
            if not all([name, unique_id, command_topic, payload_on]):
                return
            
            # Avoid duplicates
            if unique_id in scenes:
                _LOGGER.debug("Scene %s already exists, skipping", unique_id)
                return
            
            _LOGGER.info("🧩 Discovered Lytiva scene: %s (%s) in area: %s", name, unique_id, suggested_area)
            
            scene_entity = LytivaScene(
                name, 
                unique_id, 
                command_topic, 
                state_topic, 
                payload_on, 
                mqtt,
                suggested_area,
                device_info
            )
            scenes[unique_id] = scene_entity
            
            # Register in central tracking
            data["entities_by_unique_id"][f"lytiva_scene_{unique_id}"] = scene_entity
            
            async_add_entities([scene_entity], update_before_add=False)
            
        except Exception as e:
            _LOGGER.error("Error parsing Lytiva scene config: %s", e, exc_info=True)
    
    # Register callback with central discovery system
    data["register_other_callback"](on_discovery)
    
    _LOGGER.info("📡 Lytiva scene platform registered for discovery")


class LytivaScene(Scene):
    """Representation of a Lytiva MQTT Scene."""
    
    def __init__(self, name, unique_id, command_topic, state_topic, payload_on, mqtt_client, suggested_area=None, device_info=None):
        self._name = name
        self._unique_id = unique_id
        self._command_topic = command_topic
        self._state_topic = state_topic
        self._payload_on = payload_on
        self._mqtt = mqtt_client
        self._available = True
        self._suggested_area = suggested_area
        self._device_info = device_info
        
        # Listen to state topic to mark availability
        if self._state_topic:
            def on_state_message(client, userdata, msg):
                try:
                    self._available = True
                    self.hass.add_job(self.async_write_ha_state)
                except Exception as e:
                    _LOGGER.error("Error handling scene state: %s", e)
            
            self._mqtt.subscribe(self._state_topic)
            self._mqtt.message_callback_add(self._state_topic, on_state_message)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def unique_id(self) -> str:
        return f"lytiva_scene_{self._unique_id}"
    
    @property
    def available(self) -> bool:
        return self._available
    
    @property
    def suggested_area(self) -> str | None:
        """Return the suggested area for this scene."""
        return self._suggested_area
    
    @property
    def device_info(self):
        """Return device info to link this scene to a device/room."""
        if self._device_info:
            return {
                "identifiers": {(DOMAIN, self._device_info.get("identifiers", [None])[0])},
                "name": self._device_info.get("name"),
                "manufacturer": self._device_info.get("manufacturer", "Lytiva"),
                "model": self._device_info.get("model", "Scene Controller"),
                "suggested_area": self._device_info.get("suggested_area"),
            }
        return None
    
    async def async_activate(self, **kwargs) -> None:
        """Activate the scene."""
        try:
            _LOGGER.info("🎬 Activating Lytiva scene: %s", self._name)
            self._mqtt.publish(self._command_topic, self._payload_on, qos=1)
        except Exception as e:
            _LOGGER.error("Failed to activate scene %s: %s", self._name, e)