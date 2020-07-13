"""Support for Template lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_LIGHTS,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.script import Script

from . import extract_entities, initialise_templates
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

CONF_ON_ACTION = "turn_on"
CONF_OFF_ACTION = "turn_off"
CONF_LEVEL_ACTION = "set_level"
CONF_LEVEL_TEMPLATE = "level_template"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_TEMPERATURE_ACTION = "set_temperature"
CONF_COLOR_TEMPLATE = "color_template"
CONF_COLOR_ACTION = "set_color"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"
CONF_WHITE_VALUE_ACTION = "set_white_value"

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_LEVEL_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_LEVEL_TEMPLATE): cv.template,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_COLOR_TEMPLATE): cv.template,
        vol.Optional(CONF_COLOR_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_WHITE_VALUE_ACTION): cv.SCRIPT_SCHEMA,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA)}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template Lights."""
    lights = []

    for device, device_config in config[CONF_LIGHTS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)

        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]

        level_action = device_config.get(CONF_LEVEL_ACTION)
        level_template = device_config.get(CONF_LEVEL_TEMPLATE)

        temperature_action = device_config.get(CONF_TEMPERATURE_ACTION)
        temperature_template = device_config.get(CONF_TEMPERATURE_TEMPLATE)

        color_action = device_config.get(CONF_COLOR_ACTION)
        color_template = device_config.get(CONF_COLOR_TEMPLATE)

        white_value_action = device_config.get(CONF_WHITE_VALUE_ACTION)
        white_value_template = device_config.get(CONF_WHITE_VALUE_TEMPLATE)

        templates = {
            CONF_VALUE_TEMPLATE: state_template,
            CONF_ICON_TEMPLATE: icon_template,
            CONF_ENTITY_PICTURE_TEMPLATE: entity_picture_template,
            CONF_AVAILABILITY_TEMPLATE: availability_template,
            CONF_LEVEL_TEMPLATE: level_template,
            CONF_TEMPERATURE_TEMPLATE: temperature_template,
            CONF_COLOR_TEMPLATE: color_template,
            CONF_WHITE_VALUE_TEMPLATE: white_value_template,
        }

        initialise_templates(hass, templates)
        entity_ids = extract_entities(
            device, "light", device_config.get(CONF_ENTITY_ID), templates
        )

        lights.append(
            LightTemplate(
                hass,
                device,
                friendly_name,
                state_template,
                icon_template,
                entity_picture_template,
                availability_template,
                on_action,
                off_action,
                level_action,
                level_template,
                entity_ids,
                temperature_action,
                temperature_template,
                color_action,
                color_template,
                white_value_action,
                white_value_template,
            )
        )

    async_add_entities(lights)


class LightTemplate(LightEntity):
    """Representation of a templated Light, including dimmable."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        icon_template,
        entity_picture_template,
        availability_template,
        on_action,
        off_action,
        level_action,
        level_template,
        entity_ids,
        temperature_action,
        temperature_template,
        color_action,
        color_template,
        white_value_action,
        white_value_template,
    ):
        """Initialize the light."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._template = state_template
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._availability_template = availability_template
        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)
        self._level_script = None
        if level_action is not None:
            self._level_script = Script(hass, level_action)
        self._level_template = level_template
        self._temperature_script = None
        if temperature_action is not None:
            self._temperature_script = Script(hass, temperature_action)
        self._temperature_template = temperature_template
        self._color_script = None
        if color_action is not None:
            self._color_script = Script(hass, color_action)
        self._color_template = color_template
        self._white_value_script = None
        if white_value_action is not None:
            self._white_value_script = Script(hass, white_value_action)
        self._white_value_template = white_value_template

        self._state = False
        self._icon = None
        self._entity_picture = None
        self._brightness = None
        self._temperature = None
        self._color = None
        self._white_value = None
        self._entities = entity_ids
        self._available = True

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._temperature

    @property
    def white_value(self):
        """Return the white value."""
        return self._white_value

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._color

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if self._level_script is not None:
            supported_features |= SUPPORT_BRIGHTNESS
        if self._temperature_script is not None:
            supported_features |= SUPPORT_COLOR_TEMP
        if self._color_script is not None:
            supported_features |= SUPPORT_COLOR
        if self._white_value_script is not None:
            supported_features |= SUPPORT_WHITE_VALUE
        return supported_features

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_light_state_listener(event):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_light_startup(event):
            """Update template on startup."""
            if (
                self._template is not None
                or self._level_template is not None
                or self._temperature_template is not None
                or self._color_template is not None
                or self._white_value_template is not None
                or self._availability_template is not None
            ):
                if self._entities != MATCH_ALL:
                    # Track state change only for valid templates
                    async_track_state_change_event(
                        self.hass, self._entities, template_light_state_listener
                    )

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_light_startup
        )

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        optimistic_set = False
        # set optimistic states
        if self._template is None:
            self._state = True
            optimistic_set = True

        if self._level_template is None and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.info(
                "Optimistically setting brightness to %s", kwargs[ATTR_BRIGHTNESS]
            )
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            optimistic_set = True

        if self._white_value_template is None and ATTR_WHITE_VALUE in kwargs:
            _LOGGER.info(
                "Optimistically setting white value to %s", kwargs[ATTR_WHITE_VALUE]
            )
            self._white_value = kwargs[ATTR_WHITE_VALUE]
            optimistic_set = True

        if self._temperature_template is None and ATTR_COLOR_TEMP in kwargs:
            _LOGGER.info(
                "Optimistically setting color temperature to %s",
                kwargs[ATTR_COLOR_TEMP],
            )
            self._temperature = kwargs[ATTR_COLOR_TEMP]
            optimistic_set = True

        if ATTR_BRIGHTNESS in kwargs and self._level_script:
            await self._level_script.async_run(
                {"brightness": kwargs[ATTR_BRIGHTNESS]}, context=self._context
            )
        elif ATTR_COLOR_TEMP in kwargs and self._temperature_script:
            await self._temperature_script.async_run(
                {"color_temp": kwargs[ATTR_COLOR_TEMP]}, context=self._context
            )
        elif ATTR_WHITE_VALUE in kwargs and self._white_value_script:
            await self._white_value_script.async_run(
                {"white_value": kwargs[ATTR_WHITE_VALUE]}, context=self._context
            )
        elif ATTR_HS_COLOR in kwargs and self._color_script:
            hs_value = kwargs[ATTR_HS_COLOR]
            await self._color_script.async_run(
                {"hs": hs_value, "h": int(hs_value[0]), "s": int(hs_value[1])},
                context=self._context,
            )
        else:
            await self._on_script.async_run()

        if optimistic_set:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._off_script.async_run(context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()

    async def async_update(self):
        """Update from templates."""
        self.update_state()

        self.update_brightness()

        self.update_temperature()

        self.update_color()

        self.update_white_value()

        for property_name, template in (
            ("_icon", self._icon_template),
            ("_entity_picture", self._entity_picture_template),
            ("_available", self._availability_template),
        ):
            if template is None:
                continue

            try:
                value = template.async_render()
                if property_name == "_available":
                    value = value.lower() == "true"
                setattr(self, property_name, value)
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace("_", " ")
                if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"
                ):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning(
                        "Could not render %s template %s, the state is unknown",
                        friendly_property_name,
                        self._name,
                    )
                    return

                try:
                    setattr(self, property_name, getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error(
                        "Could not render %s template %s: %s",
                        friendly_property_name,
                        self._name,
                        ex,
                    )

    @callback
    def update_brightness(self):
        """Update the brightness from the template."""
        if self._level_template is None:
            return
        try:
            brightness = self._level_template.async_render()
            if brightness in ("None", ""):
                self._brightness = None
                return
            if 0 <= int(brightness) <= 255:
                self._brightness = int(brightness)
            else:
                _LOGGER.error(
                    "Received invalid brightness : %s. Expected: 0-255", brightness
                )
                self._brightness = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer brightness from 0-255, or 'None'",
                exc_info=True,
            )
            self._brightness = None
        except TemplateError:
            _LOGGER.error("Invalid template", exc_info=True)
            self._brightness = None

    @callback
    def update_white_value(self):
        """Update the white value from the template."""
        if self._white_value_template is None:
            return
        try:
            white_value = self._white_value_template.async_render()
            if white_value in ("None", ""):
                self._white_value = None
                return
            if 0 <= int(white_value) <= 255:
                self._white_value = int(white_value)
            else:
                _LOGGER.error(
                    "Received invalid white value: %s. Expected: 0-255", white_value
                )
                self._white_value = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer white_value from 0-255, or 'None'",
                exc_info=True,
            )
            self._white_value = None
        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None

    @callback
    def update_state(self):
        """Update the state from the template."""
        if self._template is None:
            return
        try:
            state = self._template.async_render().lower()
            if state in _VALID_STATES:
                self._state = state in ("true", STATE_ON)
            else:
                _LOGGER.error(
                    "Received invalid light is_on state: %s. Expected: %s",
                    state,
                    ", ".join(_VALID_STATES),
                )
                self._state = None
        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None

    @callback
    def update_temperature(self):
        """Update the temperature from the template."""
        if self._temperature_template is None:
            return
        try:
            render = self._temperature_template.async_render()
            if render in ("None", ""):
                self._temperature = None
                return
            temperature = int(render)
            if self.min_mireds <= temperature <= self.max_mireds:
                self._temperature = temperature
            else:
                _LOGGER.error(
                    "Received invalid color temperature : %s. Expected: 0-%s",
                    temperature,
                    self.max_mireds,
                )
                self._temperature = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer temperature within the range for this light, or 'None'",
                exc_info=True,
            )
            self._temperature = None
        except TemplateError:
            _LOGGER.error("Cannot evaluate temperature template", exc_info=True)
            self._temperature = None

    @callback
    def update_color(self):
        """Update the hs_color from the template."""
        if self._color_template is None:
            return

        try:
            render = self._color_template.async_render()
            if render in ("None", ""):
                self._color = None
                return
            h_str, s_str = map(
                float, render.replace("(", "").replace(")", "").split(",", 1)
            )
            if (
                h_str is not None
                and s_str is not None
                and 0 <= h_str <= 360
                and 0 <= s_str <= 100
            ):
                self._color = (h_str, s_str)
            elif h_str is not None and s_str is not None:
                _LOGGER.error(
                    "Received invalid hs_color : (%s, %s). Expected: (0-360, 0-100)",
                    h_str,
                    s_str,
                )
                self._color = None
            else:
                _LOGGER.error("Received invalid hs_color : (%s)", render)
                self._color = None
        except TemplateError:
            _LOGGER.error("Cannot evaluate hs_color template", exc_info=True)
            self._color = None
