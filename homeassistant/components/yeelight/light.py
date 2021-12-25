"""Light platform support for yeelight."""
from __future__ import annotations

import asyncio
import logging
import math

import voluptuous as vol
import yeelight
from yeelight import Bulb, Flow, RGBTransition, SleepTransition, flows
from yeelight.enums import BulbType, LightType, PowerMode, SceneClass
from yeelight.main import BulbException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_UNKNOWN,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
import homeassistant.util.color as color_util
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from . import YEELIGHT_FLOW_TRANSITION_SCHEMA
from .const import (
    ACTION_RECOVER,
    ATTR_ACTION,
    ATTR_COUNT,
    ATTR_MODE_MUSIC,
    ATTR_TRANSITIONS,
    CONF_FLOW_PARAMS,
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DATA_CONFIG_ENTRIES,
    DATA_CUSTOM_EFFECTS,
    DATA_DEVICE,
    DATA_UPDATED,
    DOMAIN,
    MODELS_WITH_DELAYED_ON_TRANSITION,
    POWER_STATE_CHANGE_TIME,
)
from .entity import YeelightEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_YEELIGHT = SUPPORT_TRANSITION | SUPPORT_FLASH | SUPPORT_EFFECT

ATTR_MINUTES = "minutes"

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_MUSIC_MODE = "set_music_mode"
SERVICE_START_FLOW = "start_flow"
SERVICE_SET_COLOR_SCENE = "set_color_scene"
SERVICE_SET_HSV_SCENE = "set_hsv_scene"
SERVICE_SET_COLOR_TEMP_SCENE = "set_color_temp_scene"
SERVICE_SET_COLOR_FLOW_SCENE = "set_color_flow_scene"
SERVICE_SET_AUTO_DELAY_OFF_SCENE = "set_auto_delay_off_scene"

EFFECT_DISCO = "Disco"
EFFECT_TEMP = "Slow Temp"
EFFECT_STROBE = "Strobe epilepsy!"
EFFECT_STROBE_COLOR = "Strobe color"
EFFECT_ALARM = "Alarm"
EFFECT_POLICE = "Police"
EFFECT_POLICE2 = "Police2"
EFFECT_CHRISTMAS = "Christmas"
EFFECT_RGB = "RGB"
EFFECT_RANDOM_LOOP = "Random Loop"
EFFECT_FAST_RANDOM_LOOP = "Fast Random Loop"
EFFECT_LSD = "LSD"
EFFECT_SLOWDOWN = "Slowdown"
EFFECT_WHATSAPP = "WhatsApp"
EFFECT_FACEBOOK = "Facebook"
EFFECT_TWITTER = "Twitter"
EFFECT_STOP = "Stop"
EFFECT_HOME = "Home"
EFFECT_NIGHT_MODE = "Night Mode"
EFFECT_DATE_NIGHT = "Date Night"
EFFECT_MOVIE = "Movie"
EFFECT_SUNRISE = "Sunrise"
EFFECT_SUNSET = "Sunset"
EFFECT_ROMANCE = "Romance"
EFFECT_HAPPY_BIRTHDAY = "Happy Birthday"
EFFECT_CANDLE_FLICKER = "Candle Flicker"

YEELIGHT_TEMP_ONLY_EFFECT_LIST = [EFFECT_TEMP, EFFECT_STOP]

YEELIGHT_MONO_EFFECT_LIST = [
    EFFECT_DISCO,
    EFFECT_STROBE,
    EFFECT_ALARM,
    EFFECT_POLICE2,
    EFFECT_WHATSAPP,
    EFFECT_FACEBOOK,
    EFFECT_TWITTER,
    EFFECT_HOME,
    EFFECT_CANDLE_FLICKER,
    *YEELIGHT_TEMP_ONLY_EFFECT_LIST,
]

YEELIGHT_COLOR_EFFECT_LIST = [
    EFFECT_STROBE_COLOR,
    EFFECT_POLICE,
    EFFECT_CHRISTMAS,
    EFFECT_RGB,
    EFFECT_RANDOM_LOOP,
    EFFECT_FAST_RANDOM_LOOP,
    EFFECT_LSD,
    EFFECT_SLOWDOWN,
    EFFECT_NIGHT_MODE,
    EFFECT_DATE_NIGHT,
    EFFECT_MOVIE,
    EFFECT_SUNRISE,
    EFFECT_SUNSET,
    EFFECT_ROMANCE,
    EFFECT_HAPPY_BIRTHDAY,
    *YEELIGHT_MONO_EFFECT_LIST,
]

EFFECTS_MAP = {
    EFFECT_DISCO: flows.disco,
    EFFECT_TEMP: flows.temp,
    EFFECT_STROBE: flows.strobe,
    EFFECT_STROBE_COLOR: flows.strobe_color,
    EFFECT_ALARM: flows.alarm,
    EFFECT_POLICE: flows.police,
    EFFECT_POLICE2: flows.police2,
    EFFECT_CHRISTMAS: flows.christmas,
    EFFECT_RGB: flows.rgb,
    EFFECT_RANDOM_LOOP: flows.random_loop,
    EFFECT_LSD: flows.lsd,
    EFFECT_SLOWDOWN: flows.slowdown,
    EFFECT_HOME: flows.home,
    EFFECT_NIGHT_MODE: flows.night_mode,
    EFFECT_DATE_NIGHT: flows.date_night,
    EFFECT_MOVIE: flows.movie,
    EFFECT_SUNRISE: flows.sunrise,
    EFFECT_SUNSET: flows.sunset,
    EFFECT_ROMANCE: flows.romance,
    EFFECT_HAPPY_BIRTHDAY: flows.happy_birthday,
    EFFECT_CANDLE_FLICKER: flows.candle_flicker,
}

VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Range(min=1, max=100))

SERVICE_SCHEMA_SET_MODE = {
    vol.Required(ATTR_MODE): vol.In([mode.name.lower() for mode in PowerMode])
}

SERVICE_SCHEMA_SET_MUSIC_MODE = {vol.Required(ATTR_MODE_MUSIC): cv.boolean}

SERVICE_SCHEMA_START_FLOW = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_COLOR_SCENE = {
    vol.Required(ATTR_RGB_COLOR): vol.All(
        vol.Coerce(tuple), vol.ExactSequence((cv.byte, cv.byte, cv.byte))
    ),
    vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_HSV_SCENE = {
    vol.Required(ATTR_HS_COLOR): vol.All(
        vol.Coerce(tuple),
        vol.ExactSequence(
            (
                vol.All(vol.Coerce(float), vol.Range(min=0, max=359)),
                vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            )
        ),
    ),
    vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE = {
    vol.Required(ATTR_KELVIN): vol.All(vol.Coerce(int), vol.Range(min=1700, max=6500)),
    vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE = {
    vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
    vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}


@callback
def _transitions_config_parser(transitions):
    """Parse transitions config into initialized objects."""
    transition_objects = []
    for transition_config in transitions:
        transition, params = list(transition_config.items())[0]
        transition_objects.append(getattr(yeelight, transition)(*params))

    return transition_objects


@callback
def _parse_custom_effects(effects_config):
    effects = {}
    for config in effects_config:
        params = config[CONF_FLOW_PARAMS]
        action = Flow.actions[params[ATTR_ACTION]]
        transitions = _transitions_config_parser(params[ATTR_TRANSITIONS])

        effects[config[CONF_NAME]] = {
            ATTR_COUNT: params[ATTR_COUNT],
            ATTR_ACTION: action,
            ATTR_TRANSITIONS: transitions,
        }

    return effects


def _async_cmd(func):
    """Define a wrapper to catch exceptions from the bulb."""

    async def _async_wrap(self, *args, **kwargs):
        for attempts in range(2):
            try:
                _LOGGER.debug("Calling %s with %s %s", func, args, kwargs)
                return await func(self, *args, **kwargs)
            except asyncio.TimeoutError as ex:
                # The wifi likely dropped, so we want to retry once since
                # python-yeelight will auto reconnect
                exc_message = str(ex) or type(ex)
                if attempts == 0:
                    continue
                raise HomeAssistantError(
                    f"Timed out when calling {func.__name__} for bulb {self.device.name} at {self.device.host}: {exc_message}"
                ) from ex
            except OSError as ex:
                # A network error happened, the bulb is likely offline now
                self.device.async_mark_unavailable()
                self.async_state_changed()
                exc_message = str(ex) or type(ex)
                raise HomeAssistantError(
                    f"Error when calling {func.__name__} for bulb {self.device.name} at {self.device.host}: {exc_message}"
                ) from ex
            except BulbException as ex:
                # The bulb likely responded but had an error
                exc_message = str(ex) or type(ex)
                raise HomeAssistantError(
                    f"Error when calling {func.__name__} for bulb {self.device.name} at {self.device.host}: {exc_message}"
                ) from ex

    return _async_wrap


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Yeelight from a config entry."""
    custom_effects = _parse_custom_effects(hass.data[DOMAIN][DATA_CUSTOM_EFFECTS])

    device = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][config_entry.entry_id][DATA_DEVICE]
    _LOGGER.debug("Adding %s", device.name)

    nl_switch_light = device.config.get(CONF_NIGHTLIGHT_SWITCH)

    lights = []

    device_type = device.type

    def _lights_setup_helper(klass):
        lights.append(klass(device, config_entry, custom_effects=custom_effects))

    if device_type == BulbType.White:
        _lights_setup_helper(YeelightGenericLight)
    elif device_type == BulbType.Color:
        if nl_switch_light and device.is_nightlight_supported:
            _lights_setup_helper(YeelightColorLightWithNightlightSwitch)
            _lights_setup_helper(YeelightNightLightModeWithoutBrightnessControl)
        else:
            _lights_setup_helper(YeelightColorLightWithoutNightlightSwitch)
    elif device_type == BulbType.WhiteTemp:
        if nl_switch_light and device.is_nightlight_supported:
            _lights_setup_helper(YeelightWithNightLight)
            _lights_setup_helper(YeelightNightLightMode)
        else:
            _lights_setup_helper(YeelightWhiteTempWithoutNightlightSwitch)
    elif device_type == BulbType.WhiteTempMood:
        if nl_switch_light and device.is_nightlight_supported:
            _lights_setup_helper(YeelightNightLightModeWithAmbientSupport)
            _lights_setup_helper(YeelightWithAmbientAndNightlight)
        else:
            _lights_setup_helper(YeelightWithAmbientWithoutNightlight)
        _lights_setup_helper(YeelightAmbientLight)
    else:
        _lights_setup_helper(YeelightGenericLight)
        _LOGGER.warning(
            "Cannot determine device type for %s, %s. Falling back to white only",
            device.host,
            device.name,
        )

    async_add_entities(lights)
    _async_setup_services(hass)


@callback
def _async_setup_services(hass: HomeAssistant):
    """Set up custom services."""

    async def _async_start_flow(entity, service_call):
        params = {**service_call.data}
        params.pop(ATTR_ENTITY_ID)
        params[ATTR_TRANSITIONS] = _transitions_config_parser(params[ATTR_TRANSITIONS])
        await entity.async_start_flow(**params)

    async def _async_set_color_scene(entity, service_call):
        await entity.async_set_scene(
            SceneClass.COLOR,
            *service_call.data[ATTR_RGB_COLOR],
            service_call.data[ATTR_BRIGHTNESS],
        )

    async def _async_set_hsv_scene(entity, service_call):
        await entity.async_set_scene(
            SceneClass.HSV,
            *service_call.data[ATTR_HS_COLOR],
            service_call.data[ATTR_BRIGHTNESS],
        )

    async def _async_set_color_temp_scene(entity, service_call):
        await entity.async_set_scene(
            SceneClass.CT,
            service_call.data[ATTR_KELVIN],
            service_call.data[ATTR_BRIGHTNESS],
        )

    async def _async_set_color_flow_scene(entity, service_call):
        flow = Flow(
            count=service_call.data[ATTR_COUNT],
            action=Flow.actions[service_call.data[ATTR_ACTION]],
            transitions=_transitions_config_parser(service_call.data[ATTR_TRANSITIONS]),
        )
        await entity.async_set_scene(SceneClass.CF, flow)

    async def _async_set_auto_delay_off_scene(entity, service_call):
        await entity.async_set_scene(
            SceneClass.AUTO_DELAY_OFF,
            service_call.data[ATTR_BRIGHTNESS],
            service_call.data[ATTR_MINUTES],
        )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_MODE, SERVICE_SCHEMA_SET_MODE, "async_set_mode"
    )
    platform.async_register_entity_service(
        SERVICE_START_FLOW, SERVICE_SCHEMA_START_FLOW, _async_start_flow
    )
    platform.async_register_entity_service(
        SERVICE_SET_COLOR_SCENE, SERVICE_SCHEMA_SET_COLOR_SCENE, _async_set_color_scene
    )
    platform.async_register_entity_service(
        SERVICE_SET_HSV_SCENE, SERVICE_SCHEMA_SET_HSV_SCENE, _async_set_hsv_scene
    )
    platform.async_register_entity_service(
        SERVICE_SET_COLOR_TEMP_SCENE,
        SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE,
        _async_set_color_temp_scene,
    )
    platform.async_register_entity_service(
        SERVICE_SET_COLOR_FLOW_SCENE,
        SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE,
        _async_set_color_flow_scene,
    )
    platform.async_register_entity_service(
        SERVICE_SET_AUTO_DELAY_OFF_SCENE,
        SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE,
        _async_set_auto_delay_off_scene,
    )
    platform.async_register_entity_service(
        SERVICE_SET_MUSIC_MODE, SERVICE_SCHEMA_SET_MUSIC_MODE, "async_set_music_mode"
    )


class YeelightGenericLight(YeelightEntity, LightEntity):
    """Representation of a Yeelight generic light."""

    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
    _attr_should_poll = False

    def __init__(self, device, entry, custom_effects=None):
        """Initialize the Yeelight light."""
        super().__init__(device, entry)

        self.config = device.config

        self._color_temp = None
        self._effect = None

        model_specs = self._bulb.get_model_specs()
        self._min_mireds = kelvin_to_mired(model_specs["color_temp"]["max"])
        self._max_mireds = kelvin_to_mired(model_specs["color_temp"]["min"])

        self._light_type = LightType.Main

        if custom_effects:
            self._custom_effects = custom_effects
        else:
            self._custom_effects = {}

        self._unexpected_state_check = None

    @callback
    def async_state_changed(self):
        """Call when the device changes state."""
        if not self._device.available:
            self._async_cancel_pending_state_check()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DATA_UPDATED.format(self._device.host),
                self.async_state_changed,
            )
        )
        await super().async_added_to_hass()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_YEELIGHT

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._predefined_effects + self.custom_effects_names

    @property
    def color_temp(self) -> int:
        """Return the color temperature."""
        if temp_in_k := self._get_property("ct"):
            self._color_temp = kelvin_to_mired(int(temp_in_k))
        return self._color_temp

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.device.name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._get_property(self._power_property) == "on"

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 1..255."""
        # Always use "bright" as property name in music mode
        # Since music mode states are only caches in upstream library
        # and the cache key is always "bright" for brightness
        brightness_property = (
            "bright" if self._bulb.music_mode else self._brightness_property
        )
        brightness = self._get_property(brightness_property) or 0
        return round(255 * (int(brightness) / 100))

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return maximum supported color temperature."""
        return self._max_mireds

    @property
    def custom_effects(self):
        """Return dict with custom effects."""
        return self._custom_effects

    @property
    def custom_effects_names(self):
        """Return list with custom effects names."""
        return list(self.custom_effects)

    @property
    def light_type(self):
        """Return light type."""
        return self._light_type

    @property
    def hs_color(self) -> tuple:
        """Return the color property."""
        hue = self._get_property("hue")
        sat = self._get_property("sat")
        if hue is None or sat is None:
            return None

        return (int(hue), int(sat))

    @property
    def rgb_color(self) -> tuple:
        """Return the color property."""
        if (rgb := self._get_property("rgb")) is None:
            return None

        rgb = int(rgb)
        blue = rgb & 0xFF
        green = (rgb >> 8) & 0xFF
        red = (rgb >> 16) & 0xFF

        return (red, green, blue)

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect if self.device.is_color_flow_enabled else None

    @property
    def _bulb(self) -> Bulb:
        return self.device.bulb

    @property
    def _properties(self) -> dict:
        return self._bulb.last_properties if self._bulb else {}

    def _get_property(self, prop, default=None):
        return self._properties.get(prop, default)

    @property
    def _brightness_property(self):
        return "bright"

    @property
    def _power_property(self):
        return "power"

    @property
    def _turn_on_power_mode(self):
        return PowerMode.LAST

    @property
    def _predefined_effects(self):
        return YEELIGHT_MONO_EFFECT_LIST

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = {
            "flowing": self.device.is_color_flow_enabled,
            "music_mode": self._bulb.music_mode,
        }

        if self.device.is_nightlight_supported:
            attributes["night_light"] = self.device.is_nightlight_enabled

        return attributes

    @property
    def device(self):
        """Return yeelight device."""
        return self._device

    async def async_update(self):
        """Update light properties."""
        await self.device.async_update(True)

    async def async_set_music_mode(self, music_mode) -> None:
        """Set the music mode on or off."""
        try:
            await self._async_set_music_mode(music_mode)
        except AssertionError as ex:
            _LOGGER.error("Unable to turn on music mode, consider disabling it: %s", ex)

    @_async_cmd
    async def _async_set_music_mode(self, music_mode) -> None:
        """Set the music mode on or off wrapped with _async_cmd."""
        bulb = self._bulb
        method = bulb.stop_music if not music_mode else bulb.start_music
        await self.hass.async_add_executor_job(method)

    @_async_cmd
    async def async_set_brightness(self, brightness, duration) -> None:
        """Set bulb brightness."""
        if not brightness:
            return
        if (
            math.floor(self.brightness) == math.floor(brightness)
            and self._bulb.model not in MODELS_WITH_DELAYED_ON_TRANSITION
        ):
            _LOGGER.debug("brightness already set to: %s", brightness)
            # Already set, and since we get pushed updates
            # we avoid setting it again to ensure we do not
            # hit the rate limit
            return

        _LOGGER.debug("Setting brightness: %s", brightness)
        await self._bulb.async_set_brightness(
            brightness / 255 * 100, duration=duration, light_type=self.light_type
        )

    @_async_cmd
    async def async_set_hs(self, hs_color, duration) -> None:
        """Set bulb's color."""
        if not hs_color or COLOR_MODE_HS not in self.supported_color_modes:
            return
        if (
            not self.device.is_color_flow_enabled
            and self.color_mode == COLOR_MODE_HS
            and self.hs_color == hs_color
        ):
            _LOGGER.debug("HS already set to: %s", hs_color)
            # Already set, and since we get pushed updates
            # we avoid setting it again to ensure we do not
            # hit the rate limit
            return

        _LOGGER.debug("Setting HS: %s", hs_color)
        await self._bulb.async_set_hsv(
            hs_color[0], hs_color[1], duration=duration, light_type=self.light_type
        )

    @_async_cmd
    async def async_set_rgb(self, rgb, duration) -> None:
        """Set bulb's color."""
        if not rgb or COLOR_MODE_RGB not in self.supported_color_modes:
            return
        if (
            not self.device.is_color_flow_enabled
            and self.color_mode == COLOR_MODE_RGB
            and self.rgb_color == rgb
        ):
            _LOGGER.debug("RGB already set to: %s", rgb)
            # Already set, and since we get pushed updates
            # we avoid setting it again to ensure we do not
            # hit the rate limit
            return

        _LOGGER.debug("Setting RGB: %s", rgb)
        await self._bulb.async_set_rgb(
            *rgb, duration=duration, light_type=self.light_type
        )

    @_async_cmd
    async def async_set_colortemp(self, colortemp, duration) -> None:
        """Set bulb's color temperature."""
        if not colortemp or COLOR_MODE_COLOR_TEMP not in self.supported_color_modes:
            return
        temp_in_k = mired_to_kelvin(colortemp)

        if (
            not self.device.is_color_flow_enabled
            and self.color_mode == COLOR_MODE_COLOR_TEMP
            and self.color_temp == colortemp
        ):
            _LOGGER.debug("Color temp already set to: %s", temp_in_k)
            # Already set, and since we get pushed updates
            # we avoid setting it again to ensure we do not
            # hit the rate limit
            return

        await self._bulb.async_set_color_temp(
            temp_in_k, duration=duration, light_type=self.light_type
        )

    @_async_cmd
    async def async_set_default(self) -> None:
        """Set current options as default."""
        await self._bulb.async_set_default()

    @_async_cmd
    async def async_set_flash(self, flash) -> None:
        """Activate flash."""
        if not flash:
            return
        if int(self._bulb.last_properties["color_mode"]) != 1:
            _LOGGER.error("Flash supported currently only in RGB mode")
            return

        transition = int(self.config[CONF_TRANSITION])
        if flash == FLASH_LONG:
            count = 1
            duration = transition * 5
        if flash == FLASH_SHORT:
            count = 1
            duration = transition * 2

        red, green, blue = color_util.color_hs_to_RGB(*self.hs_color)

        transitions = []
        transitions.append(RGBTransition(255, 0, 0, brightness=10, duration=duration))
        transitions.append(SleepTransition(duration=transition))
        transitions.append(
            RGBTransition(
                red, green, blue, brightness=self.brightness, duration=duration
            )
        )

        flow = Flow(count=count, transitions=transitions)
        await self._bulb.async_start_flow(flow, light_type=self.light_type)

    @_async_cmd
    async def async_set_effect(self, effect) -> None:
        """Activate effect."""
        if not effect:
            return

        if effect == EFFECT_STOP:
            await self._bulb.async_stop_flow(light_type=self.light_type)
            return

        if effect in self.custom_effects_names:
            flow = Flow(**self.custom_effects[effect])
        elif effect in EFFECTS_MAP:
            flow = EFFECTS_MAP[effect]()
        elif effect == EFFECT_FAST_RANDOM_LOOP:
            flow = flows.random_loop(duration=250)
        elif effect == EFFECT_WHATSAPP:
            flow = flows.pulse(37, 211, 102, count=2)
        elif effect == EFFECT_FACEBOOK:
            flow = flows.pulse(59, 89, 152, count=2)
        elif effect == EFFECT_TWITTER:
            flow = flows.pulse(0, 172, 237, count=2)
        else:
            return

        await self._bulb.async_start_flow(flow, light_type=self.light_type)
        self._effect = effect

    @_async_cmd
    async def _async_turn_on(self, duration) -> None:
        """Turn on the bulb for with a transition duration wrapped with _async_cmd."""
        await self._bulb.async_turn_on(
            duration=duration,
            light_type=self.light_type,
            power_mode=self._turn_on_power_mode,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        flash = kwargs.get(ATTR_FLASH)
        effect = kwargs.get(ATTR_EFFECT)

        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s

        if not self.is_on:
            await self._async_turn_on(duration)

        if self.config[CONF_MODE_MUSIC] and not self._bulb.music_mode:
            await self.async_set_music_mode(True)

        await self.async_set_hs(hs_color, duration)
        await self.async_set_rgb(rgb, duration)
        await self.async_set_colortemp(colortemp, duration)
        await self.async_set_brightness(brightness, duration)
        await self.async_set_flash(flash)
        await self.async_set_effect(effect)

        # save the current state if we had a manual change.
        if self.config[CONF_SAVE_ON_CHANGE] and (brightness or colortemp or rgb):
            await self.async_set_default()

        self._async_schedule_state_check(True)

    @callback
    def _async_cancel_pending_state_check(self):
        """Cancel a pending state check."""
        if self._unexpected_state_check:
            self._unexpected_state_check()
            self._unexpected_state_check = None

    @callback
    def _async_schedule_state_check(self, expected_power_state):
        """Schedule a poll if the change failed to get pushed back to us.

        Some devices (mainly nightlights) will not send back the on state
        so we need to force a refresh.
        """
        self._async_cancel_pending_state_check()

        async def _async_update_if_state_unexpected(*_):
            self._unexpected_state_check = None
            if self.is_on != expected_power_state:
                await self.device.async_update(True)

        self._unexpected_state_check = async_call_later(
            self.hass, POWER_STATE_CHANGE_TIME, _async_update_if_state_unexpected
        )

    @_async_cmd
    async def _async_turn_off(self, duration) -> None:
        """Turn off with a given transition duration wrapped with _async_cmd."""
        await self._bulb.async_turn_off(duration=duration, light_type=self.light_type)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off."""
        if not self.is_on:
            return

        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s

        await self._async_turn_off(duration)
        self._async_schedule_state_check(False)

    @_async_cmd
    async def async_set_mode(self, mode: str):
        """Set a power mode."""
        await self._bulb.async_set_power_mode(PowerMode[mode.upper()])
        self._async_schedule_state_check(True)

    @_async_cmd
    async def async_start_flow(self, transitions, count=0, action=ACTION_RECOVER):
        """Start flow."""
        flow = Flow(count=count, action=Flow.actions[action], transitions=transitions)
        await self._bulb.async_start_flow(flow, light_type=self.light_type)

    @_async_cmd
    async def async_set_scene(self, scene_class, *args):
        """
        Set the light directly to the specified state.

        If the light is off, it will first be turned on.
        """
        await self._bulb.async_set_scene(scene_class, *args)


class YeelightColorLightSupport(YeelightGenericLight):
    """Representation of a Color Yeelight light support."""

    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS, COLOR_MODE_RGB}

    @property
    def color_mode(self):
        """Return the color mode."""
        color_mode = int(self._get_property("color_mode"))
        if color_mode == 1:  # RGB
            return COLOR_MODE_RGB
        if color_mode == 2:  # color temperature
            return COLOR_MODE_COLOR_TEMP
        if color_mode == 3:  # hsv
            return COLOR_MODE_HS
        _LOGGER.debug("Light reported unknown color mode: %s", color_mode)
        return COLOR_MODE_UNKNOWN

    @property
    def _predefined_effects(self):
        return YEELIGHT_COLOR_EFFECT_LIST


class YeelightWhiteTempLightSupport:
    """Representation of a White temp Yeelight light."""

    _attr_color_mode = COLOR_MODE_COLOR_TEMP
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP}

    @property
    def _predefined_effects(self):
        return YEELIGHT_TEMP_ONLY_EFFECT_LIST


class YeelightNightLightSupport:
    """Representation of a Yeelight nightlight support."""

    @property
    def _turn_on_power_mode(self):
        return PowerMode.NORMAL


class YeelightWithoutNightlightSwitchMixIn:
    """A mix-in for yeelights without a nightlight switch."""

    @property
    def _brightness_property(self):
        # If the nightlight is not active, we do not
        # want to "current_brightness" since it will check
        # "bg_power" and main light could still be on
        if self.device.is_nightlight_enabled:
            return "nl_br"
        return super()._brightness_property

    @property
    def color_temp(self) -> int:
        """Return the color temperature."""
        if self.device.is_nightlight_enabled:
            # Enabling the nightlight locks the colortemp to max
            return self._max_mireds
        return super().color_temp


class YeelightColorLightWithoutNightlightSwitch(
    YeelightColorLightSupport,
    YeelightWithoutNightlightSwitchMixIn,
    YeelightGenericLight,
):
    """Representation of a Color Yeelight light."""


class YeelightColorLightWithNightlightSwitch(
    YeelightNightLightSupport, YeelightColorLightSupport, YeelightGenericLight
):
    """Representation of a Yeelight with rgb support and nightlight.

    It represents case when nightlight switch is set to light.
    """

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return super().is_on and not self.device.is_nightlight_enabled


class YeelightWhiteTempWithoutNightlightSwitch(
    YeelightWhiteTempLightSupport,
    YeelightWithoutNightlightSwitchMixIn,
    YeelightGenericLight,
):
    """White temp light, when nightlight switch is not set to light."""


class YeelightWithNightLight(
    YeelightNightLightSupport, YeelightWhiteTempLightSupport, YeelightGenericLight
):
    """Representation of a Yeelight with temp only support and nightlight.

    It represents case when nightlight switch is set to light.
    """

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return super().is_on and not self.device.is_nightlight_enabled


class YeelightNightLightMode(YeelightGenericLight):
    """Representation of a Yeelight when in nightlight mode."""

    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        unique = super().unique_id
        return f"{unique}-nightlight"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self.device.name} Nightlight"

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:weather-night"

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return super().is_on and self.device.is_nightlight_enabled

    @property
    def _brightness_property(self):
        return "nl_br"

    @property
    def _turn_on_power_mode(self):
        return PowerMode.MOONLIGHT

    @property
    def supported_features(self):
        """Flag no supported features."""
        return 0


class YeelightNightLightModeWithAmbientSupport(YeelightNightLightMode):
    """Representation of a Yeelight, with ambient support, when in nightlight mode."""

    @property
    def _power_property(self):
        return "main_power"


class YeelightNightLightModeWithoutBrightnessControl(YeelightNightLightMode):
    """Representation of a Yeelight, when in nightlight mode.

    It represents case when nightlight mode brightness control is not supported.
    """

    _attr_color_mode = COLOR_MODE_ONOFF
    _attr_supported_color_modes = {COLOR_MODE_ONOFF}


class YeelightWithAmbientWithoutNightlight(YeelightWhiteTempWithoutNightlightSwitch):
    """Representation of a Yeelight which has ambilight support.

    And nightlight switch type is none.
    """

    @property
    def _power_property(self):
        return "main_power"


class YeelightWithAmbientAndNightlight(YeelightWithNightLight):
    """Representation of a Yeelight which has ambilight support.

    And nightlight switch type is set to light.
    """

    @property
    def _power_property(self):
        return "main_power"


class YeelightAmbientLight(YeelightColorLightWithoutNightlightSwitch):
    """Representation of a Yeelight ambient light."""

    PROPERTIES_MAPPING = {"color_mode": "bg_lmode"}

    def __init__(self, *args, **kwargs):
        """Initialize the Yeelight Ambient light."""
        super().__init__(*args, **kwargs)
        self._min_mireds = kelvin_to_mired(6500)
        self._max_mireds = kelvin_to_mired(1700)

        self._light_type = LightType.Ambient

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        unique = super().unique_id
        return f"{unique}-ambilight"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self.device.name} Ambilight"

    @property
    def _brightness_property(self):
        return "bright"

    def _get_property(self, prop, default=None):
        if not (bg_prop := self.PROPERTIES_MAPPING.get(prop)):
            bg_prop = f"bg_{prop}"

        return super()._get_property(bg_prop, default)
