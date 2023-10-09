"""Support for Haus-Bus lights."""
import colorsys
from typing import Any, cast

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.de.hausbus.homeassistant.proxy.Dimmer import Dimmer
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOff import (
    EvOff as DimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOn import EvOn as DimmerEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.Status import (
    Status as DimmerStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Led import Led
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOff import EvOff as ledEvOff
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOn import EvOn as ledEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.Status import Status as ledStatus
from pyhausbus.de.hausbus.homeassistant.proxy.RGBDimmer import RGBDimmer
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOff import (
    EvOff as rgbDimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOn import (
    EvOn as rgbDimmerEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.Status import (
    Status as rgbDimmerStatus,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    DOMAIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .channel import HausbusChannel
from .const import ATTR_ON_STATE, DOMAIN as HAUSBUSDOMAIN
from .device import HausbusDevice
from .event_handler import IEventHandler


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus lights from a config entry."""
    gateway = cast(IEventHandler, hass.data[HAUSBUSDOMAIN][config_entry.entry_id])

    @callback
    async def async_add_light(channel: HausbusChannel) -> None:
        """Add light from Haus-Bus."""
        entities: list[HausbusLight] = []
        if isinstance(channel, HausbusLight):
            entities.append(channel)
        async_add_entities(entities)

    gateway.register_platform_add_channel_callback(async_add_light, DOMAIN)


class HausbusLight(HausbusChannel, LightEntity):
    """Representation of a Haus-Bus light."""

    TYPE = DOMAIN

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: ABusFeature,
    ) -> None:
        """Set up light."""
        super().__init__(channel.__class__.__name__, instance_id, device)

        self._state = 0
        self._brightness = 255
        self._hs = (0, 0)
        self._channel = channel

        self._attr_supported_color_modes: set[ColorMode] = set()

        if isinstance(self._channel, Dimmer):
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            cast(Dimmer, self._channel.getStatus())
        if isinstance(self._channel, Led):
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            cast(Led, self._channel.getStatus())
        if isinstance(self._channel, RGBDimmer):
            self._attr_supported_color_modes.add(ColorMode.HS)
            cast(RGBDimmer, self._channel.getStatus())

    def set_light_color(self, red: int, green: int, blue: int):
        """Set the brightness of a light channel."""
        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 100.0,
            green / 100.0,
            blue / 100.0,
        )
        params = {
            ATTR_ON_STATE: 1,
            ATTR_BRIGHTNESS: round(value * 255),
            ATTR_HS_COLOR: (round(hue * 360), round(saturation * 100)),
        }
        self.async_update_callback(**params)

    def set_light_brightness(self, brightness: int):
        """Set the brightness of a light channel."""
        params = {ATTR_ON_STATE: 1, ATTR_BRIGHTNESS: (brightness * 255) // 100}
        self.async_update_callback(**params)

    def light_turn_off(self):
        """Turn off a light channel."""
        params = {
            ATTR_ON_STATE: 0,
        }
        self.async_update_callback(**params)

    @staticmethod
    def handle_light_event(data: Any, channel: HausbusChannel):
        """Handle light events from Haus-Bus."""
        if not isinstance(channel, HausbusLight):
            return
        # dimmer event handling
        if isinstance(data, DimmerEvOn):
            event = cast(DimmerEvOn, data)
            channel.set_light_brightness(event.getBrightness())
        if isinstance(data, DimmerStatus):
            event = cast(DimmerStatus, data)
            if event.getBrightness() > 0:
                channel.set_light_brightness(event.getBrightness())
            else:
                channel.light_turn_off()
        # rgb dimmmer event handling
        if isinstance(data, rgbDimmerEvOn):
            event = cast(rgbDimmerEvOn, data)
            channel.set_light_color(
                event.getBrightnessRed(),
                event.getBrightnessGreen(),
                event.getBrightnessBlue(),
            )
        if isinstance(data, rgbDimmerStatus):
            event = cast(rgbDimmerStatus, data)
            if (
                event.getBrightnessBlue() > 0
                or event.getBrightnessGreen() > 0
                or event.getBrightnessRed() > 0
            ):
                channel.set_light_color(
                    event.getBrightnessRed(),
                    event.getBrightnessGreen(),
                    event.getBrightnessBlue(),
                )
            else:
                channel.light_turn_off()
        # led event handling
        if isinstance(data, ledEvOn):
            event = cast(ledEvOn, data)
            channel.set_light_brightness(event.getBrightness())
        if isinstance(data, ledStatus):
            event = cast(ledStatus, data)
            if event.getBrightness() > 0:
                channel.set_light_brightness(event.getBrightness())
            else:
                channel.light_turn_off()
        # light off events
        if isinstance(data, (DimmerEvOff, ledEvOff, rgbDimmerEvOff)):
            channel.light_turn_off()

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if isinstance(self._channel, (Dimmer, Led)):
            color_mode = ColorMode.BRIGHTNESS
        elif isinstance(self._channel, RGBDimmer):
            color_mode = ColorMode.HS
        else:
            color_mode = ColorMode.ONOFF
        return color_mode

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and satuartion of this light."""
        return self._hs

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state == 1

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        h_s = kwargs.get(ATTR_HS_COLOR, self._hs)

        light = self._channel
        if isinstance(light, Dimmer):
            light = cast(Dimmer, light)
            brightness = brightness * 100 // 255
            light.setBrightness(brightness, 0)
        elif isinstance(light, Led):
            light = cast(Led, light)
            brightness = brightness * 100 // 255
            light.setBrightness(brightness, 0)
        elif isinstance(self._channel, RGBDimmer):
            light = cast(RGBDimmer, light)
            rgb = colorsys.hsv_to_rgb(h_s[0] / 360, h_s[1] / 100, brightness / 255)
            red, green, blue = tuple(round(x * 100) for x in rgb)
            light.setColor(red, green, blue, 0)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        light = self._channel
        if isinstance(light, Dimmer):
            light = cast(Dimmer, light)
            light.setBrightness(0, 0)
        elif isinstance(light, Led):
            light = cast(Led, light)
            light.setBrightness(0, 0)
        elif isinstance(light, RGBDimmer):
            light = cast(RGBDimmer, light)
            light.setColor(0, 0, 0, 0)
        self._state = 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        self.turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        self.turn_off()

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Light state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs:
            if self._state != kwargs[ATTR_ON_STATE]:
                self._state = kwargs[ATTR_ON_STATE]
                state_changed = True

        if ATTR_BRIGHTNESS in kwargs:
            if self._brightness != kwargs[ATTR_BRIGHTNESS]:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                state_changed = True

        if ATTR_HS_COLOR in kwargs:
            if self._hs != kwargs[ATTR_HS_COLOR]:
                self._hs = kwargs[ATTR_HS_COLOR]
                state_changed = True

        if state_changed:
            self.schedule_update_ha_state()
