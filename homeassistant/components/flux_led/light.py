"""Support for FluxLED/MagicHome lights."""
from __future__ import annotations

from functools import partial
import logging
import random
from typing import Any

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODE,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_DEVICES,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PROTOCOL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_util

from . import FluxLedUpdateCoordinator
from .const import CONF_AUTOMATIC_ADD, CONF_CUSTOM_EFFECT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"

SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR
MODE_RGB = "rgb"
MODE_RGBW = "rgbw"
MODE_RGBCW = "rgbcw"
MODE_RGBWW = "rgbww"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"

# Constant color temp values for 2 flux_led special modes
# Warm-white and Cool-white modes
COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF = 285

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"

EFFECT_MAP = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}
EFFECT_CUSTOM_CODE = 0x60

TRANSITION_GRADUAL = "gradual"
TRANSITION_JUMP = "jump"
TRANSITION_STROBE = "strobe"

FLUX_EFFECT_LIST = sorted(EFFECT_MAP) + [EFFECT_RANDOM]

SERVICE_CUSTOM_EFFECT = "set_custom_effect"

CUSTOM_EFFECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLORS): vol.All(
            cv.ensure_list,
            vol.Length(min=1, max=16),
            [
                vol.All(
                    vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple)
                )
            ],
        ),
        vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
            vol.Range(min=0, max=100), vol.Coerce(int)
        ),
        vol.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): vol.All(
            cv.string, vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
        ),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_MODE, default=MODE_RGBW): vol.All(
            cv.string, vol.In([MODE_RGBW, MODE_RGB, MODE_WHITE])
        ),
        vol.Optional(CONF_PROTOCOL): vol.All(cv.string, vol.In(["ledenet"])),
        vol.Optional(CONF_CUSTOM_EFFECT): CUSTOM_EFFECT_SCHEMA,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Flux lights."""
    for ipaddr, device_config in config.get(CONF_DEVICES, {}).items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_HOST: ipaddr,
                    CONF_NAME: device_config[CONF_NAME],
                    CONF_PROTOCOL: device_config.get(CONF_PROTOCOL),
                    CONF_MODE: device_config[ATTR_MODE],
                    CONF_CUSTOM_EFFECT: device_config.get(CONF_CUSTOM_EFFECT),
                },
            )
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # register custom_effect service
    platform = entity_platform.current_platform.get()
    assert platform is not None
    platform.async_register_entity_service(
        SERVICE_CUSTOM_EFFECT,
        CUSTOM_EFFECT_SCHEMA,
        "set_custom_effect",
    )

    async_add_entities(
        [
            FluxLight(
                coordinator,
                entry.unique_id,
                entry.data[CONF_NAME],
            )
        ]
    )


class FluxLight(CoordinatorEntity, LightEntity):
    """Representation of a Flux light."""

    coordinator: FluxLedUpdateCoordinator

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ):
        """Initialize the light."""
        super().__init__(coordinator)
        self._name = name
        self._unique_id = unique_id
        self._state = False
        self._brightness = None
        self._hs_color: tuple[float, float] | None = None
        self._white_value = None
        self._current_effect = None
        self._last_brightness = None
        self._last_hs_color: tuple[float, float] | None = None
        self._ip_address = coordinator.host
        self._mode: str | None = None
        self._bulb: WifiLedBulb = coordinator.device

    @property
    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._bulb.isOn()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._mode == MODE_WHITE:
            return self.white_value

        return self._bulb.brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return color_util.color_RGB_to_hs(*self._bulb.getRgb())

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._mode == MODE_RGBW:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE | SUPPORT_COLOR_TEMP

        if self._mode == MODE_WHITE:
            return SUPPORT_BRIGHTNESS

        return SUPPORT_FLUX_LED

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._bulb.getRgbw()[3]

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._bulb.raw_state[3]

        if current_mode == EFFECT_CUSTOM_CODE:
            return EFFECT_CUSTOM

        for effect, code in EFFECT_MAP.items():
            if current_mode == code:
                return effect

        return None

    @property
    def extra_state_attributes(self):
        """Return the attributes."""
        return {"ip_address": self._ip_address}

    @property
    def device_info(self):
        """Return the device information."""
        if not self._unique_id:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: "FluxLED/Magic Home",
            ATTR_MODEL: "LED Lights",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        await self.hass.async_add_executor_job(partial(self._turn_on, **kwargs))
        await self.coordinator.async_request_refresh()

    def _turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turnOn()

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb: tuple[int, int, int] | None = color_util.color_hs_to_RGB(*hs_color)
        else:
            rgb = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)

        # handle special modes
        if color_temp is not None:
            if brightness is None:
                brightness = self.brightness
            if color_temp > COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF:
                self._bulb.setRgbw(w=brightness)
            else:
                self._bulb.setRgbw(w2=brightness)
            return

        # Show warning if effect set with rgb, brightness, or white level
        if effect and (brightness or white or rgb):
            _LOGGER.warning(
                "RGB, brightness and white level are ignored when"
                " an effect is specified for a flux bulb"
            )

        # Random color effect
        if effect == EFFECT_RANDOM:
            self._bulb.setRgb(
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            )
            return

        # Effect selection
        if effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)
            return

        # Preserve current brightness on color/white level change
        if brightness is None:
            brightness = self.brightness

        # Preserve color on brightness/white level change
        if rgb is None:
            rgb = self._bulb.getRgb()

        if white is None and self._mode == MODE_RGBW:
            white = self.white_value

        # handle W only mode (use brightness instead of white value)
        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        # handle RGBW mode
        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        # handle RGB mode
        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

    async def async_turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        await self.hass.async_add_executor_job(self._bulb.turnOff)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        """Fetch the data from this light bulb."""
        if self._bulb.protocol:
            if self._bulb.raw_state[9] == self._bulb.raw_state[11]:
                self._mode = MODE_RGBWW
            else:
                self._mode = MODE_RGBCW
        elif self._bulb.mode == "ww":
            self._mode = MODE_WHITE
        elif self._bulb.rgbwcapable and not self._bulb.rgbwprotocol:
            self._mode = MODE_RGBW
        else:
            self._mode = MODE_RGB

        self._hs_color = color_util.color_RGB_to_hs(*self._bulb.getRgb())

        self._current_effect = self._bulb.raw_state[3]

        if self._bulb.is_on:
            self._state = True
        else:
            self._state = False

        if self._state:
            self._last_hs_color = self._hs_color

        super()._handle_coordinator_update()
