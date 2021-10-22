"""Support for deCONZ lights."""

from __future__ import annotations

from pydeconz.light import Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_XY,
    DOMAIN,
    EFFECT_COLORLOOP,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.color import color_hs_to_xy

from .const import DOMAIN as DECONZ_DOMAIN, NEW_GROUP, NEW_LIGHT, POWER_PLUGS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

DECONZ_GROUP = "is_deconz_group"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ lights and groups from a config entry."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_light(lights=gateway.api.lights.values()):
        """Add light from deCONZ."""
        entities = []

        for light in lights:
            if (
                isinstance(light, Light)
                and light.type not in POWER_PLUGS
                and light.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzLight(light, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_light
        )
    )

    @callback
    def async_add_group(groups=gateway.api.groups.values()):
        """Add group from deCONZ."""
        if not gateway.option_allow_deconz_groups:
            return

        entities = []

        for group in groups:
            if not group.lights:
                continue

            known_groups = set(gateway.entities[DOMAIN])
            new_group = DeconzGroup(group, gateway)
            if new_group.unique_id not in known_groups:
                entities.append(new_group)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_GROUP), async_add_group
        )
    )

    async_add_light()
    async_add_group()


class DeconzBaseLight(DeconzDevice, LightEntity):
    """Representation of a deCONZ light."""

    TYPE = DOMAIN

    def __init__(self, device, gateway):
        """Set up light."""
        super().__init__(device, gateway)

        self._attr_supported_color_modes = set()

        if device.color_temp is not None:
            self._attr_supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

        if device.hue is not None and device.saturation is not None:
            self._attr_supported_color_modes.add(COLOR_MODE_HS)

        if device.xy is not None:
            self._attr_supported_color_modes.add(COLOR_MODE_XY)

        if not self._attr_supported_color_modes and device.brightness is not None:
            self._attr_supported_color_modes.add(COLOR_MODE_BRIGHTNESS)

        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(COLOR_MODE_ONOFF)

        if device.brightness is not None:
            self._attr_supported_features |= SUPPORT_FLASH
            self._attr_supported_features |= SUPPORT_TRANSITION

        if device.effect is not None:
            self._attr_supported_features |= SUPPORT_EFFECT

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        if self._device.color_mode == "ct":
            color_mode = COLOR_MODE_COLOR_TEMP
        elif self._device.color_mode == "hs":
            color_mode = COLOR_MODE_HS
        elif self._device.color_mode == "xy":
            color_mode = COLOR_MODE_XY
        elif self._device.brightness is not None:
            color_mode = COLOR_MODE_BRIGHTNESS
        else:
            color_mode = COLOR_MODE_ONOFF
        return color_mode

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [EFFECT_COLORLOOP]

    @property
    def color_temp(self):
        """Return the CT color value."""
        return self._device.color_temp

    @property
    def hs_color(self) -> tuple:
        """Return the hs color value."""
        return (self._device.hue / 65535 * 360, self._device.saturation / 255 * 100)

    @property
    def xy_color(self) -> tuple | None:
        """Return the XY color value."""
        return self._device.xy

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._device.state

    async def async_turn_on(self, **kwargs):
        """Turn on light."""
        data = {"on": True}

        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs:
            data["color_temperature"] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_HS_COLOR in kwargs:
            if COLOR_MODE_XY in self._attr_supported_color_modes:
                data["xy"] = color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
            else:
                data["hue"] = int(kwargs[ATTR_HS_COLOR][0] / 360 * 65535)
                data["saturation"] = int(kwargs[ATTR_HS_COLOR][1] / 100 * 255)

        if ATTR_XY_COLOR in kwargs:
            data["xy"] = kwargs[ATTR_XY_COLOR]

        if ATTR_TRANSITION in kwargs:
            data["transition_time"] = int(kwargs[ATTR_TRANSITION] * 10)
        elif "IKEA" in self._device.manufacturer:
            data["transition_time"] = 0

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data["alert"] = "select"
                del data["on"]
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data["alert"] = "lselect"
                del data["on"]

        if ATTR_EFFECT in kwargs:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                data["effect"] = "colorloop"
            else:
                data["effect"] = "none"

        await self._device.set_state(**data)

    async def async_turn_off(self, **kwargs):
        """Turn off light."""
        if not self._device.state:
            return

        data = {"on": False}

        if ATTR_TRANSITION in kwargs:
            data["brightness"] = 0
            data["transition_time"] = int(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data["alert"] = "select"
                del data["on"]
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data["alert"] = "lselect"
                del data["on"]

        await self._device.set_state(**data)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {DECONZ_GROUP: self._device.type == "LightGroup"}


class DeconzLight(DeconzBaseLight):
    """Representation of a deCONZ light."""

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._device.max_color_temp or super().max_mireds

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._device.min_color_temp or super().min_mireds


class DeconzGroup(DeconzBaseLight):
    """Representation of a deCONZ group."""

    def __init__(self, device, gateway):
        """Set up group and create an unique id."""
        self._unique_id = f"{gateway.bridgeid}-{device.deconz_id}"
        super().__init__(device, gateway)

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._unique_id

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DECONZ_DOMAIN, self.unique_id)},
            "manufacturer": "Dresden Elektronik",
            "model": "deCONZ group",
            "name": self._device.name,
            "via_device": (DECONZ_DOMAIN, self.gateway.api.config.bridge_id),
        }

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = dict(super().extra_state_attributes)
        attributes["all_on"] = self._device.all_on

        return attributes
