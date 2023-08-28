"""Support for deCONZ lights."""
from __future__ import annotations

from typing import Any, TypedDict, TypeVar

from pydeconz.interfaces.groups import GroupHandler
from pydeconz.interfaces.lights import LightHandler
from pydeconz.models import ResourceType
from pydeconz.models.event import EventType
from pydeconz.models.group import Group
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hs_to_xy

from .const import DOMAIN as DECONZ_DOMAIN, POWER_PLUGS
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_GROUP = "is_deconz_group"
EFFECT_TO_DECONZ = {EFFECT_COLORLOOP: LightEffect.COLOR_LOOP, "None": LightEffect.NONE}
FLASH_TO_DECONZ = {FLASH_SHORT: LightAlert.SHORT, FLASH_LONG: LightAlert.LONG}

DECONZ_TO_COLOR_MODE = {
    LightColorMode.CT: ColorMode.COLOR_TEMP,
    LightColorMode.HS: ColorMode.HS,
    LightColorMode.XY: ColorMode.XY,
}

_LightDeviceT = TypeVar("_LightDeviceT", bound=Group | Light)


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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ lights and groups from a config entry."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    entity_registry = er.async_get(hass)

    # On/Off Output should be switch not light 2022.5
    for light in gateway.api.lights.lights.values():
        if light.type == ResourceType.ON_OFF_OUTPUT.value and (
            entity_id := entity_registry.async_get_entity_id(
                DOMAIN, DECONZ_DOMAIN, light.unique_id
            )
        ):
            entity_registry.async_remove(entity_id)

    @callback
    def async_add_light(_: EventType, light_id: str) -> None:
        """Add light from deCONZ."""
        light = gateway.api.lights.lights[light_id]
        if light.type in POWER_PLUGS:
            return

        async_add_entities([DeconzLight(light, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_light,
        gateway.api.lights.lights,
    )

    @callback
    def async_add_group(_: EventType, group_id: str) -> None:
        """Add group from deCONZ.

        Update group states based on its sum of related lights.
        """
        if (group := gateway.api.groups[group_id]) and not group.lights:
            return

        first = True
        for light_id in group.lights:
            if (light := gateway.api.lights.lights.get(light_id)) and light.reachable:
                group.update_color_state(light, update_all_attributes=first)
                first = False

        async_add_entities([DeconzGroup(group, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_group,
        gateway.api.groups,
    )


class DeconzBaseLight(DeconzDevice[_LightDeviceT], LightEntity):
    """Representation of a deCONZ light."""

    TYPE = DOMAIN

    def __init__(self, device: _LightDeviceT, gateway: DeconzGateway) -> None:
        """Set up light."""
        super().__init__(device, gateway)

        self.api: GroupHandler | LightHandler
        if isinstance(self._device, Light):
            self.api = self.gateway.api.lights.lights
        elif isinstance(self._device, Group):
            self.api = self.gateway.api.groups

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

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self._device.color_mode in DECONZ_TO_COLOR_MODE:
            color_mode = DECONZ_TO_COLOR_MODE[self._device.color_mode]
        elif self._device.brightness is not None:
            color_mode = ColorMode.BRIGHTNESS
        else:
            color_mode = ColorMode.ONOFF
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
            for group in self.gateway.api.groups.values():
                if self._device.resource_id in group.lights:
                    group.update_color_state(self._device)


class DeconzGroup(DeconzBaseLight[Group]):
    """Representation of a deCONZ group."""

    _attr_has_entity_name = True

    def __init__(self, device: Group, gateway: DeconzGateway) -> None:
        """Set up group and create an unique id."""
        self._attr_unique_id = f"{gateway.bridgeid}-{device.deconz_id}"
        super().__init__(device, gateway)

        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DECONZ_DOMAIN, self.unique_id)},
            manufacturer="Dresden Elektronik",
            model="deCONZ group",
            name=device.name,
            via_device=(DECONZ_DOMAIN, gateway.api.config.bridge_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        attributes = dict(super().extra_state_attributes)
        attributes["all_on"] = self._device.all_on

        return attributes
