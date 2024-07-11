"""Support for Plum Lightpad lights."""

from __future__ import annotations

from typing import Any

from plumlightpad import Plum

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plum Lightpad dimmer lights and glow rings."""

    plum: Plum = hass.data[DOMAIN][entry.entry_id]

    def setup_entities(device) -> None:
        entities: list[LightEntity] = []

        if "lpid" in device:
            lightpad = plum.get_lightpad(device["lpid"])
            entities.append(GlowRing(lightpad=lightpad))

        if "llid" in device:
            logical_load = plum.get_load(device["llid"])
            entities.append(PlumLight(load=logical_load))

        async_add_entities(entities)

    async def new_load(device):
        setup_entities(device)

    async def new_lightpad(device):
        setup_entities(device)

    device_web_session = async_get_clientsession(hass, verify_ssl=False)
    entry.async_create_background_task(
        hass,
        plum.discover(
            hass.loop,
            loadListener=new_load,
            lightpadListener=new_lightpad,
            websession=device_web_session,
        ),
        "plum.light-discover",
    )


class PlumLight(LightEntity):
    """Representation of a Plum Lightpad dimmer."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, load):
        """Initialize the light."""
        self._load = load
        self._brightness = load.level
        unique_id = f"{load.llid}.light"
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Plum",
            model="Dimmer",
            name=load.name,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to dimmerchange events."""
        self._load.add_event_listener("dimmerchange", self.dimmerchange)

    def dimmerchange(self, event):
        """Change event handler updating the brightness."""
        self._brightness = event["level"]
        self.schedule_update_ha_state()

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._brightness > 0

    @property
    def color_mode(self) -> ColorMode:
        """Flag supported features."""
        if self._load.dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._load.turn_on(kwargs[ATTR_BRIGHTNESS])
        else:
            await self._load.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._load.turn_off()


class GlowRing(LightEntity):
    """Representation of a Plum Lightpad dimmer glow ring."""

    _attr_color_mode = ColorMode.HS
    _attr_should_poll = False
    _attr_translation_key = "glow_ring"
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, lightpad):
        """Initialize the light."""
        self._lightpad = lightpad
        self._attr_name = f"{lightpad.friendly_name} Glow Ring"

        self._attr_is_on = lightpad.glow_enabled
        self._glow_intensity = lightpad.glow_intensity
        unique_id = f"{self._lightpad.lpid}.glow"
        self._attr_unique_id = unique_id

        self._red = lightpad.glow_color["red"]
        self._green = lightpad.glow_color["green"]
        self._blue = lightpad.glow_color["blue"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Plum",
            model="Glow Ring",
            name=self._attr_name,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to configchange events."""
        self._lightpad.add_event_listener("configchange", self.configchange_event)

    def configchange_event(self, event):
        """Handle Configuration change event."""
        config = event["changes"]

        self._attr_is_on = config["glowEnabled"]
        self._glow_intensity = config["glowIntensity"]

        self._red = config["glowColor"]["red"]
        self._green = config["glowColor"]["green"]
        self._blue = config["glowColor"]["blue"]
        self.schedule_update_ha_state()

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return color_util.color_RGB_to_hs(self._red, self._green, self._blue)

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return min(max(int(round(self._glow_intensity * 255, 0)), 0), 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = kwargs[ATTR_BRIGHTNESS] / 255.0
            await self._lightpad.set_config({"glowIntensity": brightness_pct})
        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            red, green, blue = color_util.color_hs_to_RGB(*hs_color)
            await self._lightpad.set_glow_color(red, green, blue, 0)
        else:
            await self._lightpad.set_config({"glowEnabled": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = kwargs[ATTR_BRIGHTNESS] / 255.0
            await self._lightpad.set_config({"glowIntensity": brightness_pct})
        else:
            await self._lightpad.set_config({"glowEnabled": False})
