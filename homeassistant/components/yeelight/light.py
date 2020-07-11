"""Light platform support for yeelight."""
import logging
from typing import Optional

import voluptuous as vol
import yeelight
from yeelight import (
    BulbException,
    Flow,
    RGBTransition,
    SleepTransition,
    transitions as yee_transitions,
)
from yeelight.enums import BulbType, LightType, PowerMode, SceneClass

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, CONF_HOST, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.util.color as color_util
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from . import (
    ACTION_RECOVER,
    ATTR_ACTION,
    ATTR_COUNT,
    ATTR_TRANSITIONS,
    CONF_CUSTOM_EFFECTS,
    CONF_FLOW_PARAMS,
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DATA_UPDATED,
    DATA_YEELIGHT,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
    YEELIGHT_FLOW_TRANSITION_SCHEMA,
    YEELIGHT_SERVICE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_DATA_KEY = f"{DATA_YEELIGHT}_lights"

SUPPORT_YEELIGHT = (
    SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION | SUPPORT_FLASH | SUPPORT_EFFECT
)

SUPPORT_YEELIGHT_WHITE_TEMP = SUPPORT_YEELIGHT | SUPPORT_COLOR_TEMP

SUPPORT_YEELIGHT_RGB = SUPPORT_YEELIGHT_WHITE_TEMP | SUPPORT_COLOR

ATTR_MINUTES = "minutes"

SERVICE_SET_MODE = "set_mode"
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

YEELIGHT_TEMP_ONLY_EFFECT_LIST = [EFFECT_TEMP, EFFECT_STOP]

YEELIGHT_MONO_EFFECT_LIST = [
    EFFECT_DISCO,
    EFFECT_STROBE,
    EFFECT_ALARM,
    EFFECT_POLICE2,
    EFFECT_WHATSAPP,
    EFFECT_FACEBOOK,
    EFFECT_TWITTER,
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
    *YEELIGHT_MONO_EFFECT_LIST,
]

EFFECTS_MAP = {
    EFFECT_DISCO: yee_transitions.disco,
    EFFECT_TEMP: yee_transitions.temp,
    EFFECT_STROBE: yee_transitions.strobe,
    EFFECT_STROBE_COLOR: yee_transitions.strobe_color,
    EFFECT_ALARM: yee_transitions.alarm,
    EFFECT_POLICE: yee_transitions.police,
    EFFECT_POLICE2: yee_transitions.police2,
    EFFECT_CHRISTMAS: yee_transitions.christmas,
    EFFECT_RGB: yee_transitions.rgb,
    EFFECT_RANDOM_LOOP: yee_transitions.randomloop,
    EFFECT_LSD: yee_transitions.lsd,
    EFFECT_SLOWDOWN: yee_transitions.slowdown,
}

VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Range(min=1, max=100))

SERVICE_SCHEMA_SET_MODE = YEELIGHT_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_MODE): vol.In([mode.name.lower() for mode in PowerMode])}
)

SERVICE_SCHEMA_START_FLOW = YEELIGHT_SERVICE_SCHEMA.extend(
    YEELIGHT_FLOW_TRANSITION_SCHEMA
)

SERVICE_SCHEMA_SET_COLOR_SCENE = YEELIGHT_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_RGB_COLOR): vol.All(
            vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple)
        ),
        vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    }
)

SERVICE_SCHEMA_SET_HSV_SCENE = YEELIGHT_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_HS_COLOR): vol.All(
            vol.ExactSequence(
                (
                    vol.All(vol.Coerce(float), vol.Range(min=0, max=359)),
                    vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                )
            ),
            vol.Coerce(tuple),
        ),
        vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    }
)

SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE = YEELIGHT_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_KELVIN): vol.All(
            vol.Coerce(int), vol.Range(min=1700, max=6500)
        ),
        vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    }
)

SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE = YEELIGHT_SERVICE_SCHEMA.extend(
    YEELIGHT_FLOW_TRANSITION_SCHEMA
)

SERVICE_SCHEMA_SET_AUTO_DELAY_OFF = YEELIGHT_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        vol.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    }
)


def _transitions_config_parser(transitions):
    """Parse transitions config into initialized objects."""
    transition_objects = []
    for transition_config in transitions:
        transition, params = list(transition_config.items())[0]
        transition_objects.append(getattr(yeelight, transition)(*params))

    return transition_objects


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


def _cmd(func):
    """Define a wrapper to catch exceptions from the bulb."""

    def _wrap(self, *args, **kwargs):
        try:
            _LOGGER.debug("Calling %s with %s %s", func, args, kwargs)
            return func(self, *args, **kwargs)
        except BulbException as ex:
            _LOGGER.error("Error when calling %s: %s", func, ex)

    return _wrap


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yeelight bulbs."""

    if not discovery_info:
        return

    if PLATFORM_DATA_KEY not in hass.data:
        hass.data[PLATFORM_DATA_KEY] = []

    device = hass.data[DATA_YEELIGHT][discovery_info[CONF_HOST]]
    _LOGGER.debug("Adding %s", device.name)

    custom_effects = _parse_custom_effects(discovery_info[CONF_CUSTOM_EFFECTS])
    nl_switch_light = (
        discovery_info.get(CONF_NIGHTLIGHT_SWITCH_TYPE) == NIGHTLIGHT_SWITCH_TYPE_LIGHT
    )

    lights = []

    device_type = device.type

    def _lights_setup_helper(klass):
        lights.append(klass(device, custom_effects=custom_effects))

    if device_type == BulbType.White:
        _lights_setup_helper(YeelightGenericLight)
    elif device_type == BulbType.Color:
        if nl_switch_light and device.is_nightlight_supported:
            _lights_setup_helper(YeelightColorLightWithNightlightSwitch)
            _lights_setup_helper(YeelightNightLightModeWithWithoutBrightnessControl)
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
            device.ipaddr,
            device.name,
        )

    hass.data[PLATFORM_DATA_KEY] += lights
    add_entities(lights, True)
    setup_services(hass)


def setup_services(hass):
    """Set up the service listeners."""

    def service_call(func):
        def service_to_entities(service):
            """Return the known entities that a service call mentions."""

            entity_ids = extract_entity_ids(hass, service)
            target_devices = [
                light
                for light in hass.data[PLATFORM_DATA_KEY]
                if light.entity_id in entity_ids
            ]

            return target_devices

        def service_to_params(service):
            """Return service call params, without entity_id."""
            return {
                key: value
                for key, value in service.data.items()
                if key != ATTR_ENTITY_ID
            }

        def wrapper(service):
            params = service_to_params(service)
            target_devices = service_to_entities(service)
            for device in target_devices:
                func(device, params)

        return wrapper

    @service_call
    def service_set_mode(target_device, params):
        target_device.set_mode(**params)

    @service_call
    def service_start_flow(target_devices, params):
        params[ATTR_TRANSITIONS] = _transitions_config_parser(params[ATTR_TRANSITIONS])
        target_devices.start_flow(**params)

    @service_call
    def service_set_color_scene(target_device, params):
        target_device.set_scene(
            SceneClass.COLOR, *[*params[ATTR_RGB_COLOR], params[ATTR_BRIGHTNESS]]
        )

    @service_call
    def service_set_hsv_scene(target_device, params):
        target_device.set_scene(
            SceneClass.HSV, *[*params[ATTR_HS_COLOR], params[ATTR_BRIGHTNESS]]
        )

    @service_call
    def service_set_color_temp_scene(target_device, params):
        target_device.set_scene(
            SceneClass.CT, params[ATTR_KELVIN], params[ATTR_BRIGHTNESS]
        )

    @service_call
    def service_set_color_flow_scene(target_device, params):
        flow = Flow(
            count=params[ATTR_COUNT],
            action=Flow.actions[params[ATTR_ACTION]],
            transitions=_transitions_config_parser(params[ATTR_TRANSITIONS]),
        )
        target_device.set_scene(SceneClass.CF, flow)

    @service_call
    def service_set_auto_delay_off_scene(target_device, params):
        target_device.set_scene(
            SceneClass.AUTO_DELAY_OFF, params[ATTR_BRIGHTNESS], params[ATTR_MINUTES]
        )

    hass.services.register(
        DOMAIN, SERVICE_SET_MODE, service_set_mode, schema=SERVICE_SCHEMA_SET_MODE
    )
    hass.services.register(
        DOMAIN, SERVICE_START_FLOW, service_start_flow, schema=SERVICE_SCHEMA_START_FLOW
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_COLOR_SCENE,
        service_set_color_scene,
        schema=SERVICE_SCHEMA_SET_COLOR_SCENE,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_HSV_SCENE,
        service_set_hsv_scene,
        schema=SERVICE_SCHEMA_SET_HSV_SCENE,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_COLOR_TEMP_SCENE,
        service_set_color_temp_scene,
        schema=SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_COLOR_FLOW_SCENE,
        service_set_color_flow_scene,
        schema=SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_AUTO_DELAY_OFF_SCENE,
        service_set_auto_delay_off_scene,
        schema=SERVICE_SCHEMA_SET_AUTO_DELAY_OFF,
    )


class YeelightGenericLight(LightEntity):
    """Representation of a Yeelight generic light."""

    def __init__(self, device, custom_effects=None):
        """Initialize the Yeelight light."""
        self.config = device.config
        self._device = device

        self._brightness = None
        self._color_temp = None
        self._hs = None
        self._effect = None

        model_specs = self._bulb.get_model_specs()
        self._min_mireds = kelvin_to_mired(model_specs["color_temp"]["max"])
        self._max_mireds = kelvin_to_mired(model_specs["color_temp"]["min"])

        self._light_type = LightType.Main

        if custom_effects:
            self._custom_effects = custom_effects
        else:
            self._custom_effects = {}

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DATA_UPDATED.format(self._device.ipaddr),
                self._schedule_immediate_update,
            )
        )

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""

        return self.device.unique_id

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self.device.available

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
        temp_in_k = self._get_property("ct")
        if temp_in_k:
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
        temp = self._get_property(self._brightness_property)
        if temp:
            self._brightness = temp
        return round(255 * (int(self._brightness) / 100))

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
        return list(self.custom_effects.keys())

    @property
    def light_type(self):
        """Return light type."""
        return self._light_type

    @property
    def hs_color(self) -> tuple:
        """Return the color property."""
        return self._hs

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    # F821: https://github.com/PyCQA/pyflakes/issues/373
    @property
    def _bulb(self) -> "Bulb":  # noqa: F821
        return self.device.bulb

    @property
    def _properties(self) -> dict:
        if self._bulb is None:
            return {}
        return self._bulb.last_properties

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
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        attributes = {"flowing": self.device.is_color_flow_enabled}
        if self.device.is_nightlight_supported:
            attributes["night_light"] = self.device.is_nightlight_enabled

        return attributes

    @property
    def device(self):
        """Return yeelight device."""
        return self._device

    def update(self):
        """Update light properties."""
        self._hs = self._get_hs_from_properties()
        if not self.device.is_color_flow_enabled:
            self._effect = None

    def _get_hs_from_properties(self):
        rgb = self._get_property("rgb")
        color_mode = self._get_property("color_mode")

        if not rgb or not color_mode:
            return None

        color_mode = int(color_mode)
        if color_mode == 2:  # color temperature
            temp_in_k = mired_to_kelvin(self.color_temp)
            return color_util.color_temperature_to_hs(temp_in_k)
        if color_mode == 3:  # hsv
            hue = int(self._get_property("hue"))
            sat = int(self._get_property("sat"))

            return (hue / 360 * 65536, sat / 100 * 255)

        rgb = int(rgb)
        blue = rgb & 0xFF
        green = (rgb >> 8) & 0xFF
        red = (rgb >> 16) & 0xFF

        return color_util.color_RGB_to_hs(red, green, blue)

    def set_music_mode(self, mode) -> None:
        """Set the music mode on or off."""
        if mode:
            self._bulb.start_music()
        else:
            self._bulb.stop_music()

    @_cmd
    def set_brightness(self, brightness, duration) -> None:
        """Set bulb brightness."""
        if brightness:
            _LOGGER.debug("Setting brightness: %s", brightness)
            self._bulb.set_brightness(
                brightness / 255 * 100, duration=duration, light_type=self.light_type
            )

    @_cmd
    def set_rgb(self, rgb, duration) -> None:
        """Set bulb's color."""
        if rgb and self.supported_features & SUPPORT_COLOR:
            _LOGGER.debug("Setting RGB: %s", rgb)
            self._bulb.set_rgb(
                rgb[0], rgb[1], rgb[2], duration=duration, light_type=self.light_type
            )

    @_cmd
    def set_colortemp(self, colortemp, duration) -> None:
        """Set bulb's color temperature."""
        if colortemp and self.supported_features & SUPPORT_COLOR_TEMP:
            temp_in_k = mired_to_kelvin(colortemp)
            _LOGGER.debug("Setting color temp: %s K", temp_in_k)

            self._bulb.set_color_temp(
                temp_in_k, duration=duration, light_type=self.light_type
            )

    @_cmd
    def set_default(self) -> None:
        """Set current options as default."""
        self._bulb.set_default()

    @_cmd
    def set_flash(self, flash) -> None:
        """Activate flash."""
        if flash:
            if self._bulb.last_properties["color_mode"] != 1:
                _LOGGER.error("Flash supported currently only in RGB mode")
                return

            transition = int(self.config[CONF_TRANSITION])
            if flash == FLASH_LONG:
                count = 1
                duration = transition * 5
            if flash == FLASH_SHORT:
                count = 1
                duration = transition * 2

            red, green, blue = color_util.color_hs_to_RGB(*self._hs)

            transitions = []
            transitions.append(
                RGBTransition(255, 0, 0, brightness=10, duration=duration)
            )
            transitions.append(SleepTransition(duration=transition))
            transitions.append(
                RGBTransition(
                    red, green, blue, brightness=self.brightness, duration=duration
                )
            )

            flow = Flow(count=count, transitions=transitions)
            try:
                self._bulb.start_flow(flow, light_type=self.light_type)
            except BulbException as ex:
                _LOGGER.error("Unable to set flash: %s", ex)

    @_cmd
    def set_effect(self, effect) -> None:
        """Activate effect."""
        if not effect:
            return

        if effect == EFFECT_STOP:
            self._bulb.stop_flow(light_type=self.light_type)
            return

        if effect in self.custom_effects_names:
            flow = Flow(**self.custom_effects[effect])
        elif effect in EFFECTS_MAP:
            flow = Flow(count=0, transitions=EFFECTS_MAP[effect]())
        elif effect == EFFECT_FAST_RANDOM_LOOP:
            flow = Flow(count=0, transitions=yee_transitions.randomloop(duration=250))
        elif effect == EFFECT_WHATSAPP:
            flow = Flow(count=2, transitions=yee_transitions.pulse(37, 211, 102))
        elif effect == EFFECT_FACEBOOK:
            flow = Flow(count=2, transitions=yee_transitions.pulse(59, 89, 152))
        elif effect == EFFECT_TWITTER:
            flow = Flow(count=2, transitions=yee_transitions.pulse(0, 172, 237))
        else:
            return

        try:
            self._bulb.start_flow(flow, light_type=self.light_type)
            self._effect = effect
        except BulbException as ex:
            _LOGGER.error("Unable to set effect: %s", ex)

    def turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgb = color_util.color_hs_to_RGB(*hs_color) if hs_color else None
        flash = kwargs.get(ATTR_FLASH)
        effect = kwargs.get(ATTR_EFFECT)

        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s

        self.device.turn_on(
            duration=duration,
            light_type=self.light_type,
            power_mode=self._turn_on_power_mode,
        )

        if self.config[CONF_MODE_MUSIC] and not self._bulb.music_mode:
            try:
                self.set_music_mode(self.config[CONF_MODE_MUSIC])
            except BulbException as ex:
                _LOGGER.error(
                    "Unable to turn on music mode, consider disabling it: %s", ex
                )

        try:
            # values checked for none in methods
            self.set_rgb(rgb, duration)
            self.set_colortemp(colortemp, duration)
            self.set_brightness(brightness, duration)
            self.set_flash(flash)
            self.set_effect(effect)
        except BulbException as ex:
            _LOGGER.error("Unable to set bulb properties: %s", ex)
            return

        # save the current state if we had a manual change.
        if self.config[CONF_SAVE_ON_CHANGE] and (brightness or colortemp or rgb):
            try:
                self.set_default()
            except BulbException as ex:
                _LOGGER.error("Unable to set the defaults: %s", ex)
                return
        self.device.update()

    def turn_off(self, **kwargs) -> None:
        """Turn off."""
        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s

        self.device.turn_off(duration=duration, light_type=self.light_type)
        self.device.update()

    def set_mode(self, mode: str):
        """Set a power mode."""
        try:
            self._bulb.set_power_mode(PowerMode[mode.upper()])
            self.device.update()
        except BulbException as ex:
            _LOGGER.error("Unable to set the power mode: %s", ex)

    def start_flow(self, transitions, count=0, action=ACTION_RECOVER):
        """Start flow."""
        try:
            flow = Flow(
                count=count, action=Flow.actions[action], transitions=transitions
            )

            self._bulb.start_flow(flow, light_type=self.light_type)
            self.device.update()
        except BulbException as ex:
            _LOGGER.error("Unable to set effect: %s", ex)

    def set_scene(self, scene_class, *args):
        """
        Set the light directly to the specified state.

        If the light is off, it will first be turned on.
        """
        try:
            self._bulb.set_scene(scene_class, *args)
            self.device.update()
        except BulbException as ex:
            _LOGGER.error("Unable to set scene: %s", ex)


class YeelightColorLightSupport:
    """Representation of a Color Yeelight light support."""

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_YEELIGHT_RGB

    @property
    def _predefined_effects(self):
        return YEELIGHT_COLOR_EFFECT_LIST


class YeelightWhiteTempLightSupport:
    """Representation of a Color Yeelight light."""

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_YEELIGHT_WHITE_TEMP

    @property
    def _predefined_effects(self):
        return YEELIGHT_TEMP_ONLY_EFFECT_LIST


class YeelightNightLightSupport:
    """Representation of a Yeelight nightlight support."""

    @property
    def _turn_on_power_mode(self):
        return PowerMode.NORMAL


class YeelightColorLightWithoutNightlightSwitch(
    YeelightColorLightSupport, YeelightGenericLight
):
    """Representation of a Color Yeelight light."""

    @property
    def _brightness_property(self):
        return "current_brightness"


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
    YeelightWhiteTempLightSupport, YeelightGenericLight
):
    """White temp light, when nightlight switch is not set to light."""

    @property
    def _brightness_property(self):
        return "current_brightness"


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

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        unique = super().unique_id

        if unique:
            return unique + "-nightlight"

        return None

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self.device.name} nightlight"

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
    def _predefined_effects(self):
        return YEELIGHT_TEMP_ONLY_EFFECT_LIST


class YeelightNightLightModeWithAmbientSupport(YeelightNightLightMode):
    """Representation of a Yeelight, with ambient support, when in nightlight mode."""

    @property
    def _power_property(self):
        return "main_power"


class YeelightNightLightModeWithWithoutBrightnessControl(YeelightNightLightMode):
    """Representation of a Yeelight, when in nightlight mode.

    It represents case when nightlight mode brightness control is not supported.
    """

    @property
    def supported_features(self):
        """Flag no supported features."""
        return 0


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
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        unique = super().unique_id

        if unique:
            return unique + "-ambilight"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self.device.name} ambilight"

    @property
    def _brightness_property(self):
        return "bright"

    def _get_property(self, prop, default=None):
        bg_prop = self.PROPERTIES_MAPPING.get(prop)

        if not bg_prop:
            bg_prop = f"bg_{prop}"

        return super()._get_property(bg_prop, default)
