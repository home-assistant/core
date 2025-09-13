"""Support for Haus-Bus lights."""

from __future__ import annotations

import colorsys
import logging
from typing import TYPE_CHECKING, Any

# from .number import HausBusNumber
from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.de.hausbus.homeassistant.proxy.Dimmer import Dimmer
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.Configuration import (
    Configuration as DimmerConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOff import (
    EvOff as DimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOn import EvOn as DimmerEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.Status import (
    Status as DimmerStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.params.EDirection import EDirection
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.params.EMode import (
    EMode as DimmerMode,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Led import Led
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.Configuration import (
    Configuration as LedConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOff import EvOff as ledEvOff
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOn import EvOn as ledEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.Status import Status as ledStatus
from pyhausbus.de.hausbus.homeassistant.proxy.LogicalButton import LogicalButton
from pyhausbus.de.hausbus.homeassistant.proxy.RGBDimmer import RGBDimmer
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.Configuration import (
    Configuration as rGBConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOff import (
    EvOff as rgbDimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOn import (
    EvOn as rgbDimmerEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.Status import (
    Status as rgbDimmerStatus,
)
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HausbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Haus-Bus lights from a config entry."""

    gateway = config_entry.runtime_data.gateway
    platform = entity_platform.async_get_current_platform()

    # Dimmer Services
    platform.async_register_entity_service(
        "dimmer_set_brightness",
        {
            vol.Required("brightness", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("duration", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_dimmer_set_brightness",
    )
    platform.async_register_entity_service(
        "dimmer_start_ramp",
        {vol.Required("direction", default="up"): vol.In(["up", "down", "toggle"])},
        "async_dimmer_start_ramp",
    )
    platform.async_register_entity_service(
        "dimmer_stop_ramp",
        {},
        "async_dimmer_stop_ramp",
    )
    platform.async_register_entity_service(
        "dimmer_set_configuration",
        {
            vol.Required("mode", default="dimm_trailing_edge"): vol.In(
                ["dimm_trailing_edge", "dimm_leading_edge", "switch_only"]
            ),
            vol.Required("dimming_time", default=12): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("ramp_time", default=60): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("dimming_start_brightness", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("dimming_end_brightness", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        "async_dimmer_set_configuration",
    )

    # RGB Services
    platform.async_register_entity_service(
        "rgb_set_color",
        {
            vol.Required("brightness_red", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required("brightness_green", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required("brightness_blue", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("duration", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_rgb_set_color",
    )
    platform.async_register_entity_service(
        "rgb_set_configuration",
        {
            vol.Required("dimming_time", default=12): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
        },
        "async_rgb_set_configuration",
    )

    # LED Services
    platform.async_register_entity_service(
        "led_off",
        {
            vol.Optional("off_delay", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_led_off",
    )
    platform.async_register_entity_service(
        "led_on",
        {
            vol.Required("brightness", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("duration", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
            vol.Optional("on_delay", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_led_on",
    )
    platform.async_register_entity_service(
        "led_blink",
        {
            vol.Required("brightness", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required("off_time", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("on_time", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Optional("quantity", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
        },
        "async_led_blink",
    )
    platform.async_register_entity_service(
        "led_set_min_brightness",
        {
            vol.Required("min_brightness", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        "async_led_set_min_brightness",
    )
    platform.async_register_entity_service(
        "led_set_configuration",
        {
            vol.Required("time_base", default=1000): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        },
        "async_led_set_configuration",
    )

    # Registriere Callback für neue Light-Entities
    async def async_add_light(channel: HausbusEntity) -> None:
        """Add light from Haus-Bus."""

        if isinstance(channel, HausbusLight):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_light, LIGHT_DOMAIN)


class HausbusLight(HausbusEntity, LightEntity):
    """Representation of a Haus-Bus light."""

    def __init__(self, channel: ABusFeature, device: HausbusDevice) -> None:
        """Set up light."""
        super().__init__(channel, device)

        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_hs_color = (0, 0)

    @staticmethod
    def percent_to_ha_brightness(percent: float) -> int:
        """Convert 0–100% to HA brightness (0–255)."""
        percent = max(0.0, min(100.0, percent))  # clamp
        return round(percent * 255 / 100)

    @staticmethod
    def ha_brightness_to_percent(brightness: int) -> float:
        """Convert HA brightness (0–255) to 0–100%."""
        brightness = max(0, min(255, brightness))  # clamp
        return round(brightness * 100 / 255)

    def set_light_color(self, red: int, green: int, blue: int) -> None:
        """Set the color of a light channel."""
        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 100.0,
            green / 100.0,
            blue / 100.0,
        )
        params = {
            ATTR_ON_STATE: True,
            ATTR_BRIGHTNESS_PCT: value,
            ATTR_HS_COLOR: (round(hue * 360), round(saturation * 100)),
        }
        self.async_update_callback(**params)

    def set_light_brightness(self, brightness: int) -> None:
        """Set the brightness of a light channel."""
        params = {ATTR_ON_STATE: True, ATTR_BRIGHTNESS_PCT: brightness / 100}
        self.async_update_callback(**params)

    def light_turn_off(self) -> None:
        """Turn off a light channel."""
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_event(self, data: Any) -> None:
        """Handle light events from Haus-Bus."""
        # light off events
        if isinstance(data, (DimmerEvOff, ledEvOff, rgbDimmerEvOff)):
            self.light_turn_off()

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Light state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if (
            ATTR_BRIGHTNESS_PCT in kwargs
            and self._attr_brightness != kwargs[ATTR_BRIGHTNESS_PCT] * 255
        ):
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS_PCT] * 255
            state_changed = True

        if ATTR_HS_COLOR in kwargs and self._attr_hs_color != kwargs[ATTR_HS_COLOR]:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()


class HausbusDimmerLight(HausbusLight):
    """Representation of a Haus-Bus dimmer."""

    def __init__(self, channel: Dimmer, device: HausbusDevice) -> None:
        """Set up light."""
        super().__init__(channel, device)

        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.setBrightness(0, 0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
        if brightness is None:
            brightness = 0

        brightness = round(brightness * 100 // 255)
        self._channel.setBrightness(brightness, 0)

    def handle_event(self, data: Any) -> None:
        """Handle dimmer events from HausBus."""
        super().handle_event(data)
        # dimmer event handling
        if isinstance(data, DimmerEvOn):
            self.set_light_brightness(data.getBrightness())
        elif isinstance(data, DimmerStatus):
            if data.getBrightness() > 0:
                self.set_light_brightness(data.getBrightness())
            else:
                self.light_turn_off()
        elif isinstance(data, DimmerConfiguration):
            self._configuration = data

            hbDimmerMode = {
                DimmerMode.DIMM_CR: "dim_trailing_edge",
                DimmerMode.DIMM_L: "dim_leading_edge",
                DimmerMode.SWITCH: "switch_only",
            }.get(data.getMode(), "switch_only")

            self._attr_extra_state_attributes["mode"] = hbDimmerMode
            self._attr_extra_state_attributes["dimming_time"] = data.getFadingTime()
            self._attr_extra_state_attributes["ramp_time"] = data.getDimmingTime()
            self._attr_extra_state_attributes["dimming_start_brightness"] = (
                data.getDimmingRangeStart()
            )
            self._attr_extra_state_attributes["dimming_end_brightness"] = (
                data.getDimmingRangeEnd()
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    async def async_dimmer_set_brightness(self, brightness: int, duration: int):
        """Setzt eine Helligkeit mit einer Dauer."""
        LOGGER.debug(
            "async_dimmer_set_brightness brightness %s, duration %s",
            brightness,
            duration,
        )
        self._channel.setBrightness(brightness, duration)

    async def async_dimmer_start_ramp(self, direction: str):
        """Starts dimming in the given direction or opposite direction than last time."""
        LOGGER.debug("async_dimmer_start_ramp direction %s", direction)
        if direction == "up":
            self._channel.start(EDirection.TO_LIGHT)
        elif direction == "down":
            self._channel.start(EDirection.TO_DARK)
        elif direction == "toggle":
            self._channel.start(EDirection.TOGGLE)

    async def async_dimmer_stop_ramp(self):
        """Stops an active dimming ramp."""
        LOGGER.debug("async_dimmer_stop_ramp")
        self._channel.stop()

    async def async_dimmer_set_configuration(
        self,
        mode: str,
        dimming_time: int,
        ramp_time: int,
        dimming_start_brightness: int,
        dimming_end_brightness: int,
    ):
        """Setzt die Konfiguration eines Dimmers."""
        LOGGER.debug(
            "async_dimmer_set_configuration mode %s, dimming_time %s, ramp_time %s, dimming_start_brightness %s, dimming_end_brightness %s",
            mode,
            dimming_time,
            ramp_time,
            dimming_start_brightness,
            dimming_end_brightness,
        )

        hbDimmerMode = {
            "dim_trailing_edge": DimmerMode.DIMM_CR,
            "dim_leading_edge": DimmerMode.DIMM_L,
            "switch_only": DimmerMode.SWITCH,
        }.get(mode, DimmerMode.SWITCH)
        self._channel.setConfiguration(
            hbDimmerMode,
            dimming_time,
            ramp_time,
            dimming_start_brightness,
            dimming_end_brightness,
        )
        self._channel.getConfiguration()


class HausbusRGBDimmerLight(HausbusLight):
    """Representation of a Haus-Bus RGB dimmer."""

    def __init__(self, channel: RGBDimmer, device: HausbusDevice) -> None:
        """Set up light."""
        super().__init__(channel, device)

        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.setColor(0, 0, 0, 0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
        h_s = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)

        if brightness is None:
            brightness = 0

        if h_s is None:
            h_s = (0, 0)

        rgb = colorsys.hsv_to_rgb(h_s[0] / 360, h_s[1] / 100, brightness / 255)
        red, green, blue = tuple(round(x * 100) for x in rgb)
        self._channel.setColor(red, green, blue, 0)

    def handle_event(self, data: Any) -> None:
        """Handle RGB dimmer events from HausBus."""
        super().handle_event(data)
        # rgb dimmmer event handling
        if isinstance(data, rgbDimmerEvOn):
            self.set_light_color(
                data.getBrightnessRed(),
                data.getBrightnessGreen(),
                data.getBrightnessBlue(),
            )
        elif isinstance(data, rgbDimmerStatus):
            if (
                data.getBrightnessBlue() > 0
                or data.getBrightnessGreen() > 0
                or data.getBrightnessRed() > 0
            ):
                self.set_light_color(
                    data.getBrightnessRed(),
                    data.getBrightnessGreen(),
                    data.getBrightnessBlue(),
                )
            else:
                self.light_turn_off()
        elif isinstance(data, rGBConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes = {}
            self._attr_extra_state_attributes["dimming_time"] = data.getFadingTime()
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    async def async_rgb_set_color(
        self,
        brightness_red: int,
        brightness_green: int,
        brightness_blue: int,
        duration: int,
    ):
        """Schaltet ein RGB Licht mit einer Dauer ein."""
        LOGGER.debug(
            "async_rgb_set_color brightnessRed %s, brightnessGreen %s, brightnessBlue %s, duration %s",
            brightness_red,
            brightness_green,
            brightness_blue,
            duration,
        )
        self._channel.setColor(
            brightness_red, brightness_green, brightness_blue, duration
        )

    async def async_rgb_set_configuration(self, dimming_time: int):
        """Setzt die Konfiguration eines RGB Dimmers."""
        LOGGER.debug("async_rgb_set_configuration dimming_time %s", dimming_time)
        self._channel.setConfiguration(dimming_time)
        self._channel.getConfiguration()


class HausbusLedLight(HausbusLight):
    """Representation of a Haus-Bus LED."""

    def __init__(self, channel: Led, device: HausbusDevice) -> None:
        """Set up light."""
        super().__init__(channel, device)

        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.off(0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)

        if brightness is None:
            brightness = 0

        brightness = round(brightness * 100 // 255)
        self._channel.on(brightness, 0, 0)

    def handle_event(self, data: Any) -> None:
        """Handle led events from HausBus."""
        super().handle_event(data)
        # led event handling
        if isinstance(data, ledEvOn):
            self.set_light_brightness(data.getBrightness())
        elif isinstance(data, ledStatus):
            if data.getBrightness() > 0:
                self.set_light_brightness(data.getBrightness())
            else:
                self.light_turn_off()
        elif isinstance(data, LedConfiguration):
            self._configuration = data
            # self._extra_state_attributes["dimm_offset"] = data.getDimmOffset()
            # self._extra_state_attributes["min_brightness"] = data.getMinBrightness()
            self._attr_extra_state_attributes["time_base"] = data.getTimeBase()
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    # SERVICES
    async def async_led_off(self, off_delay: int):
        """Schaltet eine LED mit Ausschaltverzögerung aus."""
        LOGGER.debug("async_led_off off_delay %s", off_delay)
        self._channel.off(off_delay)

    async def async_led_on(self, brightness: int, duration: int, on_delay: int):
        """Schaltet eine LED mit Einschaltverzögerung ein."""
        LOGGER.debug(
            "async_led_on brightness %s, duration %s, on_delay %s",
            brightness,
            duration,
            on_delay,
        )
        self._channel.on(brightness, duration, on_delay)

    async def async_led_blink(
        self, brightness: int, off_time: int, on_time: int, quantity: int
    ):
        """Lässt eine LED blinken."""
        LOGGER.debug(
            "async_led_blink brightness %s off_time %s on_time %s quantity %s",
            brightness,
            off_time,
            on_time,
            quantity,
        )
        self._channel.blink(brightness, off_time, on_time, quantity)

    async def async_led_set_min_brightness(self, min_brightness: int):
        """Setzt eine Mindesthelligkeit, die auch dann erhalten bleibt, wenn die LED per off ausgeschaltet wird."""
        LOGGER.debug("async_led_min_brightness min_brightness %s", min_brightness)
        self._channel.setMinBrightness(min_brightness)

    async def async_led_set_configuration(self, time_base: int):
        """Setzt die Konfiguration einer Led."""
        LOGGER.debug("async_led_set_configuration time_base %s", time_base)

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        self._channel.setConfiguration(
            self._configuration.getDimmOffset(),
            self._configuration.getMinBrightness(),
            time_base,
            self._configuration.getOptions(),
        )
        self._channel.getConfiguration()


class HausbusBackLight(HausbusLight):
    """Representation of a Haus-Bus backlight."""

    def __init__(self, channel: LogicalButton, device: HausbusDevice) -> None:
        """Set up light."""
        super().__init__(channel, device)

        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.setMinBrightness(0)
        self.light_turn_off()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)

        if brightness is None:
            brightness = 0

        brightness = round(brightness * 100 // 255)
        self._channel.setMinBrightness(brightness)
        self.set_light_brightness(brightness)
