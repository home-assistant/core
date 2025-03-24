"""Support for Osram Lightify."""

from __future__ import annotations

import logging
import random
from typing import Any

from lightify import Lightify
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_LIGHTIFY_NODES = "allow_lightify_nodes"
CONF_ALLOW_LIGHTIFY_GROUPS = "allow_lightify_groups"
CONF_ALLOW_LIGHTIFY_SENSORS = "allow_lightify_sensors"
CONF_ALLOW_LIGHTIFY_SWITCHES = "allow_lightify_switches"
CONF_INTERVAL_LIGHTIFY_STATUS = "interval_lightify_status"
CONF_INTERVAL_LIGHTIFY_CONF = "interval_lightify_conf"

DEFAULT_ALLOW_LIGHTIFY_NODES = True
DEFAULT_ALLOW_LIGHTIFY_GROUPS = True
DEFAULT_ALLOW_LIGHTIFY_SENSORS = True
DEFAULT_ALLOW_LIGHTIFY_SWITCHES = True
DEFAULT_INTERVAL_LIGHTIFY_STATUS = 5
DEFAULT_INTERVAL_LIGHTIFY_CONF = 3600

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(
            CONF_ALLOW_LIGHTIFY_NODES, default=DEFAULT_ALLOW_LIGHTIFY_NODES
        ): cv.boolean,
        vol.Optional(
            CONF_ALLOW_LIGHTIFY_GROUPS, default=DEFAULT_ALLOW_LIGHTIFY_GROUPS
        ): cv.boolean,
        vol.Optional(
            CONF_ALLOW_LIGHTIFY_SENSORS, default=DEFAULT_ALLOW_LIGHTIFY_SENSORS
        ): cv.boolean,
        vol.Optional(
            CONF_ALLOW_LIGHTIFY_SWITCHES, default=DEFAULT_ALLOW_LIGHTIFY_SWITCHES
        ): cv.boolean,
        vol.Optional(
            CONF_INTERVAL_LIGHTIFY_STATUS, default=DEFAULT_INTERVAL_LIGHTIFY_STATUS
        ): cv.positive_int,
        vol.Optional(
            CONF_INTERVAL_LIGHTIFY_CONF, default=DEFAULT_INTERVAL_LIGHTIFY_CONF
        ): cv.positive_int,
    }
)

DEFAULT_BRIGHTNESS = 2
DEFAULT_KELVIN = 2700


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Osram Lightify lights."""
    host = config[CONF_HOST]
    try:
        bridge = Lightify(host, log_level=logging.NOTSET)
    except OSError:
        _LOGGER.exception("Error connecting to bridge %s", host)
        return

    setup_bridge(bridge, add_entities, config)


def setup_bridge(bridge, add_entities, config):
    """Set up the Lightify bridge."""
    lights = {}
    groups = {}
    groups_last_updated = [0]

    def update_lights():
        """Update the lights objects with the latest info from the bridge."""
        try:
            new_lights = bridge.update_all_light_status(
                config[CONF_INTERVAL_LIGHTIFY_STATUS]
            )
            lights_changed = bridge.lights_changed()
        except TimeoutError:
            _LOGGER.error("Timeout during updating of lights")
            return 0
        except OSError:
            _LOGGER.error("OSError during updating of lights")
            return 0

        if new_lights and config[CONF_ALLOW_LIGHTIFY_NODES]:
            new_entities = []
            for addr, light in new_lights.items():
                if (
                    light.devicetype().name == "SENSOR"
                    and not config[CONF_ALLOW_LIGHTIFY_SENSORS]
                ) or (
                    light.devicetype().name == "SWITCH"
                    and not config[CONF_ALLOW_LIGHTIFY_SWITCHES]
                ):
                    continue

                if addr not in lights:
                    osram_light = OsramLightifyLight(
                        light, update_lights, lights_changed
                    )
                    lights[addr] = osram_light
                    new_entities.append(osram_light)
                else:
                    lights[addr].update_luminary(light)

            add_entities(new_entities)

        return lights_changed

    def update_groups():
        """Update the groups objects with the latest info from the bridge."""
        lights_changed = update_lights()

        try:
            bridge.update_scene_list(config[CONF_INTERVAL_LIGHTIFY_CONF])
            new_groups = bridge.update_group_list(config[CONF_INTERVAL_LIGHTIFY_CONF])
            groups_updated = bridge.groups_updated()
        except TimeoutError:
            _LOGGER.error("Timeout during updating of scenes/groups")
            return 0
        except OSError:
            _LOGGER.error("OSError during updating of scenes/groups")
            return 0

        if new_groups:
            new_groups = {group.idx(): group for group in new_groups.values()}
            new_entities = []
            for idx, group in new_groups.items():
                if idx not in groups:
                    osram_group = OsramLightifyGroup(
                        group, update_groups, groups_updated
                    )
                    groups[idx] = osram_group
                    new_entities.append(osram_group)
                else:
                    groups[idx].update_luminary(group)

            add_entities(new_entities)

        if groups_updated > groups_last_updated[0]:
            groups_last_updated[0] = groups_updated
            for idx, osram_group in groups.items():
                if idx not in new_groups:
                    osram_group.update_static_attributes()

        return max(lights_changed, groups_updated)

    update_lights()
    if config[CONF_ALLOW_LIGHTIFY_GROUPS]:
        update_groups()


class Luminary(LightEntity):
    """Representation of Luminary Lights and Groups."""

    def __init__(self, luminary, update_func, changed):
        """Initialize a Luminary Light."""
        self.update_func = update_func
        self._luminary = luminary
        self._changed = changed

        self._unique_id = None
        self._effect_list = []
        self._is_on = False
        self._available = True
        self._brightness = None
        self._rgb_color = None
        self._device_attributes = None

        self.update_static_attributes()
        self.update_dynamic_attributes()

    def _get_unique_id(self):
        """Get a unique ID (not implemented)."""
        raise NotImplementedError

    def _get_supported_color_modes(self) -> set[ColorMode]:
        """Get supported color modes."""
        color_modes: set[ColorMode] = set()
        if "temp" in self._luminary.supported_features():
            color_modes.add(ColorMode.COLOR_TEMP)

        if "rgb" in self._luminary.supported_features():
            color_modes.add(ColorMode.HS)

        if not color_modes and "lum" in self._luminary.supported_features():
            color_modes.add(ColorMode.BRIGHTNESS)

        if not color_modes:
            color_modes.add(ColorMode.ONOFF)

        return color_modes

    def _get_supported_features(self) -> LightEntityFeature:
        """Get list of supported features."""
        features = LightEntityFeature(0)
        if "lum" in self._luminary.supported_features():
            features = features | LightEntityFeature.TRANSITION

        if "temp" in self._luminary.supported_features():
            features = features | LightEntityFeature.TRANSITION

        if "rgb" in self._luminary.supported_features():
            features = (
                features | LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT
            )

        return features

    def _get_effect_list(self):
        """Get list of supported effects."""
        effects = []
        if "rgb" in self._luminary.supported_features():
            effects.append(EFFECT_RANDOM)

        return effects

    @property
    def name(self):
        """Return the name of the luminary."""
        return self._luminary.name()

    @property
    def hs_color(self):
        """Return last hs color value set."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def brightness(self):
        """Return brightness of the luminary (0..255)."""
        return self._brightness

    @property
    def is_on(self):
        """Return True if the device is on."""
        return self._is_on

    @property
    def effect_list(self):
        """List of supported effects."""
        return self._effect_list

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_attributes

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    def play_effect(self, effect, transition):
        """Play selected effect."""
        if effect == EFFECT_RANDOM:
            self._rgb_color = (
                random.randrange(0, 256),
                random.randrange(0, 256),
                random.randrange(0, 256),
            )
            self._luminary.set_rgb(*self._rgb_color, transition)
            self._luminary.set_onoff(True)
            return True

        return False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        transition = int(kwargs.get(ATTR_TRANSITION, 0) * 10)
        if ATTR_EFFECT in kwargs:
            self.play_effect(kwargs[ATTR_EFFECT], transition)
            return

        if ATTR_HS_COLOR in kwargs:
            self._rgb_color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._luminary.set_rgb(*self._rgb_color, transition)

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._luminary.set_temperature(color_temp_kelvin, transition)

        self._is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._luminary.set_luminance(int(self._brightness / 2.55), transition)
        else:
            self._luminary.set_onoff(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._is_on = False
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            self._brightness = DEFAULT_BRIGHTNESS
            self._luminary.set_luminance(0, transition)
        else:
            self._luminary.set_onoff(False)

    def update_luminary(self, luminary):
        """Update internal luminary object."""
        self._luminary = luminary
        self.update_static_attributes()

    def update_static_attributes(self) -> None:
        """Update static attributes of the luminary."""
        self._unique_id = self._get_unique_id()
        self._attr_supported_color_modes = self._get_supported_color_modes()
        self._attr_supported_features = self._get_supported_features()
        self._effect_list = self._get_effect_list()
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_max_color_temp_kelvin = (
                self._luminary.max_temp() or DEFAULT_KELVIN
            )
            self._attr_min_color_temp_kelvin = (
                self._luminary.min_temp() or DEFAULT_KELVIN
            )
        if len(self._attr_supported_color_modes) == 1:
            # The light supports only a single color mode
            self._attr_color_mode = list(self._attr_supported_color_modes)[0]

    def update_dynamic_attributes(self):
        """Update dynamic attributes of the luminary."""
        self._is_on = self._luminary.on()
        self._available = self._luminary.reachable() and not self._luminary.deleted()
        if brightness_supported(self._attr_supported_color_modes):
            self._brightness = int(self._luminary.lum() * 2.55)

        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp_kelvin = self._luminary.temp() or DEFAULT_KELVIN

        if ColorMode.HS in self._attr_supported_color_modes:
            self._rgb_color = self._luminary.rgb()

        if len(self._attr_supported_color_modes) > 1:
            # The light supports hs + color temp, determine which one it is
            if self._rgb_color == (0, 0, 0):
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                self._attr_color_mode = ColorMode.HS

    def update(self) -> None:
        """Synchronize state with bridge."""
        changed = self.update_func()
        if changed > self._changed:
            self._changed = changed
            self.update_dynamic_attributes()


class OsramLightifyLight(Luminary):
    """Representation of an Osram Lightify Light."""

    def _get_unique_id(self):
        """Get a unique ID."""
        return self._luminary.addr()

    def update_static_attributes(self):
        """Update static attributes of the luminary."""
        super().update_static_attributes()
        attrs = {
            "device_type": (
                f"{self._luminary.type_id()} ({self._luminary.devicename()})"
            ),
            "firmware_version": self._luminary.version(),
        }
        if self._luminary.devicetype().name == "SENSOR":
            attrs["sensor_values"] = self._luminary.raw_values()

        self._device_attributes = attrs


class OsramLightifyGroup(Luminary):
    """Representation of an Osram Lightify Group."""

    def _get_unique_id(self):
        """Get a unique ID for the group."""
        #       Actually, it's a wrong choice for a unique ID, because a combination of
        #       lights is NOT unique (Osram Lightify allows to create different groups
        #       with the same lights). Also a combination of lights may easily change,
        #       but the group remains the same from the user's perspective.
        #       It should be something like "<gateway host>-<group.idx()>"
        #       For now keeping it as is for backward compatibility with existing
        #       users.
        return f"{self._luminary.lights()}"

    def _get_supported_features(self) -> LightEntityFeature:
        """Get list of supported features."""
        features = super()._get_supported_features()
        if self._luminary.scenes():
            features |= LightEntityFeature.EFFECT

        return features

    def _get_effect_list(self):
        """Get list of supported effects."""
        effects = super()._get_effect_list()
        effects.extend(self._luminary.scenes())
        return sorted(effects)

    def play_effect(self, effect, transition):
        """Play selected effect."""
        if super().play_effect(effect, transition):
            return True

        if effect in self._luminary.scenes():
            self._luminary.activate_scene(effect)
            return True

        return False

    def update_static_attributes(self):
        """Update static attributes of the luminary."""
        super().update_static_attributes()
        self._device_attributes = {"lights": self._luminary.light_names()}
