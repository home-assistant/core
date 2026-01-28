"""Lytiva Light Platform."""
from __future__ import annotations

import logging
from typing import Any, Dict

import lytiva
from lytiva import LytivaDevice

from homeassistant.components import mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lytiva lights."""

    @callback
    def async_add_light(payload: dict[str, Any]) -> None:
        """Add light from discovery."""
        async_add_entities([LytivaLight(hass, entry, payload)])

    # Listen for 'lytiva_discovery_light' signal sent by __init__.py
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_discovery_light", async_add_light)
    )


class LytivaLight(LightEntity):
    """Lytiva Light Entity."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self._entry = entry
        self._config = config or {}

        # Identity
        self._attr_name = config.get("name", "Lytiva Light")
        self._attr_unique_id = str(config.get("unique_id") or config.get("address"))
        
        # Address
        addr = config.get("address") if config.get("address") not in (None, "") else self._attr_unique_id
        try:
            self.address = int(addr)
        except Exception:
            self.address = addr

        self.command_topic = config.get("command_topic")
        # Default status topic pattern if not provided
        self.state_topic = config.get("state_topic", f"LYT/homeassistant/{self.address}/status")

        # Default internal state
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color = [255, 255, 255]

        # CCT temperature: device uses mireds internally.
        self._attr_min_mireds = config.get("min_mireds", 154)
        self._attr_max_mireds = config.get("max_mireds", 370)
        self._internal_color_temp_mired = self._attr_min_mireds

        # Expose Kelvin equivalents
        self._attr_min_color_temp_kelvin = lytiva.mireds_to_kelvin(self._attr_max_mireds)
        self._attr_max_color_temp_kelvin = lytiva.mireds_to_kelvin(self._attr_min_mireds)
        self._attr_color_temp_kelvin = lytiva.mireds_to_kelvin(self._internal_color_temp_mired)

        # State memory
        self._last_brightness = 255
        self._last_color_temp_kelvin = self._attr_min_color_temp_kelvin
        self._last_rgb = [255, 255, 255]

        # Type detect
        typ = config.get("type", "")

        if "color_temp_command_topic" in config or typ == "cct":
            self.light_type = "cct"
        elif "rgb_command_topic" in config or typ == "rgb":
            self.light_type = "rgb"
        else:
            self.light_type = "dimmer"

        # Initialize Protocol Library
        self._device = LytivaDevice(
            self.address, 
            self.light_type,
            min_mireds=self._attr_min_mireds,
            max_mireds=self._attr_max_mireds
        )

        # Supported modes
        if self.light_type == "cct":
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif self.light_type == "rgb":
            self._attr_supported_color_modes = {ColorMode.RGB}
            self._attr_color_mode = ColorMode.RGB
        elif typ == "onoff":
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def device_info(self):
        """Return device info."""
        device_config = self._config.get("device", {})
        if not device_config:
             return None

        identifiers = device_config.get("identifiers")
        if identifiers and isinstance(identifiers, list):
             identifiers = {(DOMAIN, id) for id in identifiers}
        else:
             identifiers = {(DOMAIN, self._attr_unique_id)}

        return {
            "identifiers": identifiers,
            "name": device_config.get("name", self._attr_name),
            "manufacturer": device_config.get("manufacturer"),
            "model": device_config.get("model"),
            "suggested_area": device_config.get("suggested_area"),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to status updates."""
        await super().async_added_to_hass()
        
        @callback
        def message_received(msg):
            """Handle new MQTT state."""
            self.hass.async_create_task(self._update_from_payload(msg.payload))

        await mqtt.async_subscribe(self.hass, self.state_topic, message_received)

    async def _publish(self, payload: Dict[str, Any]):
        """Publish MQTT payload."""
        if not self.command_topic:
            return
        import json
        try:
            await mqtt.async_publish(self.hass, self.command_topic, json.dumps(payload))
        except Exception:
            _LOGGER.exception("Light MQTT publish error")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgb = kwargs.get(ATTR_RGB_COLOR)

        # Update local attributes for state preservation
        if brightness is not None:
            self._attr_brightness = brightness
            self._last_brightness = brightness
        if kelvin is not None:
            self._attr_color_temp_kelvin = kelvin
            self._last_color_temp_kelvin = kelvin
            self._internal_color_temp_mired = lytiva.kelvin_to_mireds(kelvin)
        if rgb is not None:
            self._attr_rgb_color = rgb
            self._last_rgb = list(rgb)

        payload = self._device.get_turn_on_payload(
            brightness=brightness or self._last_brightness,
            kelvin=kelvin or self._last_color_temp_kelvin,
            rgb=rgb or tuple(self._last_rgb)
        )

        self._attr_is_on = True
        await self._publish(payload)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        payload = self._device.get_turn_off_payload()
        self._attr_is_on = False
        await self._publish(payload)
        self.async_write_ha_state()

    async def _update_from_payload(self, payload_str: str) -> None:
        """Update state from payload using library decoder."""
        try:
            status = self._device.decode_status(payload_str)
            if not status:
                return

            if (is_on := status.get("is_on")) is not None:
                self._attr_is_on = is_on
            
            if (brightness := status.get("brightness")) is not None:
                self._attr_brightness = brightness
                if brightness > 0:
                    self._last_brightness = brightness
            
            if (kelvin := status.get("kelvin")) is not None:
                self._attr_color_temp_kelvin = int(kelvin)
                self._internal_color_temp_mired = lytiva.kelvin_to_mireds(self._attr_color_temp_kelvin)
            
            if (rgb := status.get("rgb_color")) is not None:
                self._attr_rgb_color = rgb
            
            self.async_write_ha_state()
                
        except Exception as e:
            _LOGGER.exception("Light update error: %s", e)