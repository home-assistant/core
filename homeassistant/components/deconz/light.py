"""Support for deCONZ lights."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

from pydeconz.group import DeconzGroup as Group
from pydeconz.light import (
    ALERT_LONG,
    ALERT_SHORT,
    EFFECT_COLOR_LOOP,
    EFFECT_NONE,
    Light,
)

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hs_to_xy

from .const import DOMAIN as DECONZ_DOMAIN, POWER_PLUGS
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_GROUP = "is_deconz_group"
EFFECT_TO_DECONZ = {EFFECT_COLORLOOP: EFFECT_COLOR_LOOP, "None": EFFECT_NONE}
FLASH_TO_DECONZ = {FLASH_SHORT: ALERT_SHORT, FLASH_LONG: ALERT_LONG}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ lights and groups from a config entry."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_light(
        lights: list[Light] | ValuesView[Light] = gateway.api.lights.values(),
    ) -> None:
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
            hass,
            gateway.signal_new_light,
            async_add_light,
        )
    )

    @callback
    def async_add_group(
        groups: list[Group] | ValuesView[Group] = gateway.api.groups.values(),
    ) -> None:
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
            hass,
            gateway.signal_new_group,
            async_add_group,
        )
    )

    async_add_light()
    async_add_group()


class DeconzBaseLight(DeconzDevice, LightEntity):
    """Representation of a deCONZ light."""

    TYPE = DOMAIN

    def __init__(self, device: Group | Light, gateway: DeconzGateway) -> None:
        """Set up light."""
        super().__init__(device, gateway)

        self._attr_supported_color_modes: set[str] = set()

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
            self._attr_effect_list = [EFFECT_COLORLOOP]

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
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._device.brightness  # type: ignore[no-any-return]

    @property
    def color_temp(self) -> int:
        """Return the CT color value."""
        return self._device.color_temp  # type: ignore[no-any-return]

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hs color value."""
        return (self._device.hue / 65535 * 360, self._device.saturation / 255 * 100)

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the XY color value."""
        return self._device.xy  # type: ignore[no-any-return]

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.state  # type: ignore[no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        data: dict[str, bool | float | int | str | tuple[float, float]] = {"on": True}

        if attr_brightness := kwargs.get(ATTR_BRIGHTNESS):
            data["brightness"] = attr_brightness

        if attr_color_temp := kwargs.get(ATTR_COLOR_TEMP):
            data["color_temperature"] = attr_color_temp

        if attr_hs_color := kwargs.get(ATTR_HS_COLOR):
            if COLOR_MODE_XY in self._attr_supported_color_modes:
                data["xy"] = color_hs_to_xy(*attr_hs_color)
            else:
                data["hue"] = int(attr_hs_color[0] / 360 * 65535)
                data["saturation"] = int(attr_hs_color[1] / 100 * 255)

        if ATTR_XY_COLOR in kwargs:
            data["xy"] = kwargs[ATTR_XY_COLOR]

        if attr_transition := kwargs.get(ATTR_TRANSITION):
            data["transition_time"] = int(attr_transition * 10)
        elif "IKEA" in self._device.manufacturer:
            data["transition_time"] = 0

        if (alert := FLASH_TO_DECONZ.get(kwargs.get(ATTR_FLASH, ""))) is not None:
            data["alert"] = alert
            del data["on"]

        if (effect := EFFECT_TO_DECONZ.get(kwargs.get(ATTR_EFFECT, ""))) is not None:
            data["effect"] = effect

        await self._device.set_state(**data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        if not self._device.state:
            return

        data: dict[str, bool | int | str] = {"on": False}

        if ATTR_TRANSITION in kwargs:
            data["brightness"] = 0
            data["transition_time"] = int(kwargs[ATTR_TRANSITION] * 10)

        if (alert := FLASH_TO_DECONZ.get(kwargs.get(ATTR_FLASH, ""))) is not None:
            data["alert"] = alert
            del data["on"]

        await self._device.set_state(**data)

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        return {DECONZ_GROUP: isinstance(self._device, Group)}


class DeconzLight(DeconzBaseLight):
    """Representation of a deCONZ light."""

    _device: Light

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._device.max_color_temp or super().max_mireds

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._device.min_color_temp or super().min_mireds


class DeconzGroup(DeconzBaseLight):
    """Representation of a deCONZ group."""

    _device: Group

    def __init__(self, device: Group, gateway: DeconzGateway) -> None:
        """Set up group and create an unique id."""
        self._unique_id = f"{gateway.bridgeid}-{device.deconz_id}"
        super().__init__(device, gateway)

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
            via_device=(DECONZ_DOMAIN, self.gateway.api.config.bridge_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        attributes = dict(super().extra_state_attributes)
        attributes["all_on"] = self._device.all_on

        return attributes
