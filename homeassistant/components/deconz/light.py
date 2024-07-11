"""Support for deCONZ lights."""

from __future__ import annotations

from typing import Any, TypedDict, cast

from pydeconz.interfaces.groups import GroupHandler
from pydeconz.interfaces.lights import LightHandler
from pydeconz.models.event import EventType
from pydeconz.models.group import Group, TypedGroupAction
from pydeconz.models.light.light import Light, LightAlert, LightColorMode, LightEffect

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN,
    EFFECT_COLORLOOP,
    FLASH_LONG,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hs_to_xy

from .const import DOMAIN as DECONZ_DOMAIN, POWER_PLUGS
from .deconz_device import DeconzDevice
from .hub import DeconzHub

DECONZ_GROUP = "is_deconz_group"
EFFECT_TO_DECONZ = {
    EFFECT_COLORLOOP: LightEffect.COLOR_LOOP,
    "None": LightEffect.NONE,
    # Specific to Lidl christmas light
    "carnival": LightEffect.CARNIVAL,
    "collide": LightEffect.COLLIDE,
    "fading": LightEffect.FADING,
    "fireworks": LightEffect.FIREWORKS,
    "flag": LightEffect.FLAG,
    "glow": LightEffect.GLOW,
    "rainbow": LightEffect.RAINBOW,
    "snake": LightEffect.SNAKE,
    "snow": LightEffect.SNOW,
    "sparkles": LightEffect.SPARKLES,
    "steady": LightEffect.STEADY,
    "strobe": LightEffect.STROBE,
    "twinkle": LightEffect.TWINKLE,
    "updown": LightEffect.UPDOWN,
    "vintage": LightEffect.VINTAGE,
    "waves": LightEffect.WAVES,
}
FLASH_TO_DECONZ = {FLASH_SHORT: LightAlert.SHORT, FLASH_LONG: LightAlert.LONG}

DECONZ_TO_COLOR_MODE = {
    LightColorMode.CT: ColorMode.COLOR_TEMP,
    LightColorMode.GRADIENT: ColorMode.XY,
    LightColorMode.HS: ColorMode.HS,
    LightColorMode.XY: ColorMode.XY,
}

XMAS_LIGHT_EFFECTS = [
    "carnival",
    "collide",
    "fading",
    "fireworks",
    "flag",
    "glow",
    "rainbow",
    "snake",
    "snow",
    "sparkles",
    "steady",
    "strobe",
    "twinkle",
    "updown",
    "vintage",
    "waves",
]


class SetStateAttributes(TypedDict, total=False):
    """Attributes available with set state call."""

    alert: LightAlert
    brightness: int
    color_temperature: int
    effect: LightEffect
    hue: int
    on: bool
    saturation: int
    transition_time: int
    xy: tuple[float, float]


def update_color_state(
    group: Group, lights: list[Light], override: bool = False
) -> None:
    """Sync group color state with light."""
    data = {
        attribute: light_attribute
        for light in lights
        for attribute in ("bri", "ct", "hue", "sat", "xy", "colormode", "effect")
        if (light_attribute := light.raw["state"].get(attribute)) is not None
    }

    if override:
        group.raw["action"] = cast(TypedGroupAction, data)
    else:
        group.update(cast(dict[str, dict[str, Any]], {"action": data}))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ lights and groups from a config entry."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[DOMAIN] = set()

    @callback
    def async_add_light(_: EventType, light_id: str) -> None:
        """Add light from deCONZ."""
        light = hub.api.lights.lights[light_id]
        if light.type in POWER_PLUGS:
            return

        async_add_entities([DeconzLight(light, hub)])

    hub.register_platform_add_device_callback(
        async_add_light,
        hub.api.lights.lights,
    )

    @callback
    def async_add_group(_: EventType, group_id: str) -> None:
        """Add group from deCONZ.

        Update group states based on its sum of related lights.
        """
        if (group := hub.api.groups[group_id]) and not group.lights:
            return

        lights = [
            light
            for light_id in group.lights
            if (light := hub.api.lights.lights.get(light_id)) and light.reachable
        ]
        update_color_state(group, lights, True)

        async_add_entities([DeconzGroup(group, hub)])

    hub.register_platform_add_device_callback(
        async_add_group,
        hub.api.groups,
    )


class DeconzBaseLight[_LightDeviceT: Group | Light](
    DeconzDevice[_LightDeviceT], LightEntity
):
    """Representation of a deCONZ light."""

    TYPE = DOMAIN
    _attr_color_mode = ColorMode.UNKNOWN

    def __init__(self, device: _LightDeviceT, hub: DeconzHub) -> None:
        """Set up light."""
        super().__init__(device, hub)

        self.api: GroupHandler | LightHandler
        if isinstance(self._device, Light):
            self.api = self.hub.api.lights.lights
        elif isinstance(self._device, Group):
            self.api = self.hub.api.groups

        self._attr_supported_color_modes: set[ColorMode] = set()

        if device.color_temp is not None:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

        if device.hue is not None and device.saturation is not None:
            self._attr_supported_color_modes.add(ColorMode.HS)

        if device.xy is not None:
            self._attr_supported_color_modes.add(ColorMode.XY)

        if not self._attr_supported_color_modes and device.brightness is not None:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)

        if device.brightness is not None:
            self._attr_supported_features |= (
                LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
            )

        if device.effect is not None:
            self._attr_supported_features |= LightEntityFeature.EFFECT
            self._attr_effect_list = [EFFECT_COLORLOOP]
            if device.model_id in ("HG06467", "TS0601"):
                self._attr_effect_list = XMAS_LIGHT_EFFECTS

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._device.color_mode in DECONZ_TO_COLOR_MODE:
            color_mode = DECONZ_TO_COLOR_MODE[self._device.color_mode]
        elif self._device.brightness is not None:
            color_mode = ColorMode.BRIGHTNESS
        else:
            color_mode = ColorMode.ONOFF
        if color_mode not in self._attr_supported_color_modes:
            # Some lights controlled by ZigBee scenes can get unsupported color mode
            return self._attr_color_mode
        self._attr_color_mode = color_mode
        return color_mode

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value."""
        return self._device.color_temp

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        if (hue := self._device.hue) and (sat := self._device.saturation):
            return (hue / 65535 * 360, sat / 255 * 100)
        return None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the XY color value."""
        return self._device.xy

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._device.state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        data: SetStateAttributes = {"on": True}

        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs:
            data["color_temperature"] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_HS_COLOR in kwargs:
            if ColorMode.XY in self._attr_supported_color_modes:
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

        if ATTR_FLASH in kwargs and kwargs[ATTR_FLASH] in FLASH_TO_DECONZ:
            data["alert"] = FLASH_TO_DECONZ[kwargs[ATTR_FLASH]]
            del data["on"]

        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in EFFECT_TO_DECONZ:
            data["effect"] = EFFECT_TO_DECONZ[kwargs[ATTR_EFFECT]]

        await self.api.set_state(id=self._device.resource_id, **data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        if not self._device.state:
            return

        data: SetStateAttributes = {"on": False}

        if ATTR_TRANSITION in kwargs:
            data["brightness"] = 0
            data["transition_time"] = int(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_FLASH in kwargs and kwargs[ATTR_FLASH] in FLASH_TO_DECONZ:
            data["alert"] = FLASH_TO_DECONZ[kwargs[ATTR_FLASH]]
            del data["on"]

        await self.api.set_state(id=self._device.resource_id, **data)

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        return {DECONZ_GROUP: isinstance(self._device, Group)}


class DeconzLight(DeconzBaseLight[Light]):
    """Representation of a deCONZ light."""

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._device.max_color_temp or super().max_mireds

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._device.min_color_temp or super().min_mireds

    @callback
    def async_update_callback(self) -> None:
        """Light state will also reflect in relevant groups."""
        super().async_update_callback()

        if self._device.reachable and "attr" not in self._device.changed_keys:
            for group in self.hub.api.groups.values():
                if self._device.resource_id in group.lights:
                    update_color_state(group, [self._device])


class DeconzGroup(DeconzBaseLight[Group]):
    """Representation of a deCONZ group."""

    _attr_has_entity_name = True

    def __init__(self, device: Group, hub: DeconzHub) -> None:
        """Set up group and create an unique id."""
        self._unique_id = f"{hub.bridgeid}-{device.deconz_id}"
        super().__init__(device, hub)

        self._attr_name = None

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DECONZ_DOMAIN, self.unique_id)},
            manufacturer="Dresden Elektronik",
            model="deCONZ group",
            name=self._device.name,
            via_device=(DECONZ_DOMAIN, self.hub.api.config.bridge_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        attributes = dict(super().extra_state_attributes)
        attributes["all_on"] = self._device.all_on

        return attributes
