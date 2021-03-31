"""Support for Template fans."""
import logging

import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    ENTITY_ID_FORMAT,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
    preset_modes_from_speed_list,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script
from homeassistant.helpers.template import ResultWrapper

from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)

CONF_FANS = "fans"
CONF_SPEED_LIST = "speeds"
CONF_SPEED_COUNT = "speed_count"
CONF_PRESET_MODES = "preset_modes"
CONF_SPEED_TEMPLATE = "speed_template"
CONF_PERCENTAGE_TEMPLATE = "percentage_template"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_OSCILLATING_TEMPLATE = "oscillating_template"
CONF_DIRECTION_TEMPLATE = "direction_template"
CONF_ON_ACTION = "turn_on"
CONF_OFF_ACTION = "turn_off"
CONF_SET_PERCENTAGE_ACTION = "set_percentage"
CONF_SET_SPEED_ACTION = "set_speed"
CONF_SET_OSCILLATING_ACTION = "set_oscillating"
CONF_SET_DIRECTION_ACTION = "set_direction"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"

_VALID_STATES = [STATE_ON, STATE_OFF]
_VALID_OSC = [True, False]
_VALID_DIRECTIONS = [DIRECTION_FORWARD, DIRECTION_REVERSE]

FAN_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    cv.deprecated(CONF_SPEED_LIST),
    cv.deprecated(CONF_SPEED_TEMPLATE),
    cv.deprecated(CONF_SET_SPEED_ACTION),
    vol.Schema(
        {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_SPEED_TEMPLATE): cv.template,
            vol.Optional(CONF_PERCENTAGE_TEMPLATE): cv.template,
            vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
            vol.Optional(CONF_OSCILLATING_TEMPLATE): cv.template,
            vol.Optional(CONF_DIRECTION_TEMPLATE): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_SPEED_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_PERCENTAGE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_OSCILLATING_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SET_DIRECTION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SPEED_COUNT): vol.Coerce(int),
            vol.Optional(
                CONF_SPEED_LIST,
                default=[SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH],
            ): cv.ensure_list,
            vol.Optional(CONF_PRESET_MODES): cv.ensure_list,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_FANS): cv.schema_with_slug_keys(FAN_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template Fans."""
    fans = []

    for device, device_config in config[CONF_FANS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config[CONF_VALUE_TEMPLATE]
        speed_template = device_config.get(CONF_SPEED_TEMPLATE)
        percentage_template = device_config.get(CONF_PERCENTAGE_TEMPLATE)
        preset_mode_template = device_config.get(CONF_PRESET_MODE_TEMPLATE)
        oscillating_template = device_config.get(CONF_OSCILLATING_TEMPLATE)
        direction_template = device_config.get(CONF_DIRECTION_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)

        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]
        set_speed_action = device_config.get(CONF_SET_SPEED_ACTION)
        set_percentage_action = device_config.get(CONF_SET_PERCENTAGE_ACTION)
        set_preset_mode_action = device_config.get(CONF_SET_PRESET_MODE_ACTION)
        set_oscillating_action = device_config.get(CONF_SET_OSCILLATING_ACTION)
        set_direction_action = device_config.get(CONF_SET_DIRECTION_ACTION)

        speed_list = device_config[CONF_SPEED_LIST]
        speed_count = device_config.get(CONF_SPEED_COUNT)
        preset_modes = device_config.get(CONF_PRESET_MODES)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        fans.append(
            TemplateFan(
                hass,
                device,
                friendly_name,
                state_template,
                speed_template,
                percentage_template,
                preset_mode_template,
                oscillating_template,
                direction_template,
                availability_template,
                on_action,
                off_action,
                set_speed_action,
                set_percentage_action,
                set_preset_mode_action,
                set_oscillating_action,
                set_direction_action,
                speed_count,
                speed_list,
                preset_modes,
                unique_id,
            )
        )

    return fans


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template fans."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateFan(TemplateEntity, FanEntity):
    """A template fan component."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        speed_template,
        percentage_template,
        preset_mode_template,
        oscillating_template,
        direction_template,
        availability_template,
        on_action,
        off_action,
        set_speed_action,
        set_percentage_action,
        set_preset_mode_action,
        set_oscillating_action,
        set_direction_action,
        speed_count,
        speed_list,
        preset_modes,
        unique_id,
    ):
        """Initialize the fan."""
        super().__init__(availability_template=availability_template)
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name

        self._template = state_template
        self._speed_template = speed_template
        self._percentage_template = percentage_template
        self._preset_mode_template = preset_mode_template
        self._oscillating_template = oscillating_template
        self._direction_template = direction_template
        self._supported_features = 0

        domain = __name__.split(".")[-2]

        self._on_script = Script(hass, on_action, friendly_name, domain)
        self._off_script = Script(hass, off_action, friendly_name, domain)

        self._set_speed_script = None
        if set_speed_action:
            self._set_speed_script = Script(
                hass, set_speed_action, friendly_name, domain
            )

        self._set_percentage_script = None
        if set_percentage_action:
            self._set_percentage_script = Script(
                hass, set_percentage_action, friendly_name, domain
            )

        self._set_preset_mode_script = None
        if set_preset_mode_action:
            self._set_preset_mode_script = Script(
                hass, set_preset_mode_action, friendly_name, domain
            )

        self._set_oscillating_script = None
        if set_oscillating_action:
            self._set_oscillating_script = Script(
                hass, set_oscillating_action, friendly_name, domain
            )

        self._set_direction_script = None
        if set_direction_action:
            self._set_direction_script = Script(
                hass, set_direction_action, friendly_name, domain
            )

        self._state = STATE_OFF
        self._speed = None
        self._percentage = None
        self._preset_mode = None
        self._oscillating = None
        self._direction = None

        if (
            self._speed_template
            or self._percentage_template
            or self._preset_mode_template
        ):
            self._supported_features |= SUPPORT_SET_SPEED
        if self._oscillating_template:
            self._supported_features |= SUPPORT_OSCILLATE
        if self._direction_template:
            self._supported_features |= SUPPORT_DIRECTION

        self._unique_id = unique_id

        # Number of valid speeds
        self._speed_count = speed_count

        # List of valid speeds
        self._speed_list = speed_list

        # List of valid preset modes
        self._preset_modes = preset_modes

    @property
    def _implemented_speed(self):
        """Return true if speed has been implemented."""
        return bool(self._set_speed_script or self._speed_template)

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this fan."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count or 100

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        if self._preset_modes is not None:
            return self._preset_modes
        return preset_modes_from_speed_list(self._speed_list)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._preset_mode

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return self._percentage

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillating

    @property
    def current_direction(self):
        """Return the oscillation state."""
        return self._direction

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        await self._on_script.async_run(
            {
                ATTR_SPEED: speed,
                ATTR_PERCENTAGE: percentage,
                ATTR_PRESET_MODE: preset_mode,
            },
            context=self._context,
        )
        self._state = STATE_ON

        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        elif speed is not None:
            await self.async_set_speed(speed)

    # pylint: disable=arguments-differ
    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        await self._off_script.async_run(context=self._context)
        self._state = STATE_OFF

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed not in self.speed_list:
            _LOGGER.error(
                "Received invalid speed: %s. Expected: %s", speed, self.speed_list
            )
            return

        self._state = STATE_OFF if speed == SPEED_OFF else STATE_ON
        self._speed = speed
        self._preset_mode = None
        self._percentage = self.speed_to_percentage(speed)

        if self._set_speed_script:
            await self._set_speed_script.async_run(
                {ATTR_SPEED: self._speed}, context=self._context
            )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage speed of the fan."""
        speed_list = self.speed_list
        self._state = STATE_OFF if percentage == 0 else STATE_ON
        self._speed = self.percentage_to_speed(percentage) if speed_list else None
        self._percentage = percentage
        self._preset_mode = None

        if self._set_percentage_script:
            await self._set_percentage_script.async_run(
                {ATTR_PERCENTAGE: self._percentage}, context=self._context
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset_mode of the fan."""
        if preset_mode not in self.preset_modes:
            _LOGGER.error(
                "Received invalid preset_mode: %s. Expected: %s",
                preset_mode,
                self.preset_modes,
            )
            return

        self._state = STATE_ON
        self._preset_mode = preset_mode
        self._speed = preset_mode
        self._percentage = None

        if self._set_preset_mode_script:
            await self._set_preset_mode_script.async_run(
                {ATTR_PRESET_MODE: self._preset_mode}, context=self._context
            )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation of the fan."""
        if self._set_oscillating_script is None:
            return

        if oscillating in _VALID_OSC:
            self._oscillating = oscillating
            await self._set_oscillating_script.async_run(
                {ATTR_OSCILLATING: oscillating}, context=self._context
            )
        else:
            _LOGGER.error(
                "Received invalid oscillating value: %s. Expected: %s",
                oscillating,
                ", ".join(_VALID_OSC),
            )

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if self._set_direction_script is None:
            return

        if direction in _VALID_DIRECTIONS:
            self._direction = direction
            await self._set_direction_script.async_run(
                {ATTR_DIRECTION: direction}, context=self._context
            )
        else:
            _LOGGER.error(
                "Received invalid direction: %s. Expected: %s",
                direction,
                ", ".join(_VALID_DIRECTIONS),
            )

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        # Validate state
        if result in _VALID_STATES:
            self._state = result
        elif result in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._state = None
        else:
            _LOGGER.error(
                "Received invalid fan is_on state: %s. Expected: %s",
                result,
                ", ".join(_VALID_STATES),
            )
            self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute("_state", self._template, None, self._update_state)
        if self._preset_mode_template is not None:
            self.add_template_attribute(
                "_preset_mode",
                self._preset_mode_template,
                None,
                self._update_preset_mode,
                none_on_template_error=True,
            )
        if self._percentage_template is not None:
            self.add_template_attribute(
                "_percentage",
                self._percentage_template,
                None,
                self._update_percentage,
                none_on_template_error=True,
            )
        if self._speed_template is not None:
            self.add_template_attribute(
                "_speed",
                self._speed_template,
                None,
                self._update_speed,
                none_on_template_error=True,
            )
        if self._oscillating_template is not None:
            self.add_template_attribute(
                "_oscillating",
                self._oscillating_template,
                None,
                self._update_oscillating,
                none_on_template_error=True,
            )
        if self._direction_template is not None:
            self.add_template_attribute(
                "_direction",
                self._direction_template,
                None,
                self._update_direction,
                none_on_template_error=True,
            )
        await super().async_added_to_hass()

    @callback
    def _update_speed(self, speed):
        # Validate speed
        speed = str(speed)

        if speed in self._speed_list:
            self._speed = speed
            self._percentage = self.speed_to_percentage(speed)
            self._preset_mode = speed if speed in self.preset_modes else None
        elif speed in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._speed = None
            self._percentage = 0
            self._preset_mode = None
        else:
            _LOGGER.error(
                "Received invalid speed: %s. Expected: %s", speed, self._speed_list
            )
            self._speed = None
            self._percentage = 0
            self._preset_mode = None

    @callback
    def _update_percentage(self, percentage):
        # Validate percentage
        try:
            percentage = int(float(percentage))
        except ValueError:
            _LOGGER.error("Received invalid percentage: %s", percentage)
            self._speed = None
            self._percentage = 0
            self._preset_mode = None
            return

        if 0 <= percentage <= 100:
            self._percentage = percentage
            if self._speed_list:
                self._speed = self.percentage_to_speed(percentage)
            self._preset_mode = None
        else:
            _LOGGER.error("Received invalid percentage: %s", percentage)
            self._speed = None
            self._percentage = 0
            self._preset_mode = None

    @callback
    def _update_preset_mode(self, preset_mode):
        # Validate preset mode
        preset_mode = str(preset_mode)

        if preset_mode in self.preset_modes:
            self._speed = preset_mode
            self._percentage = None
            self._preset_mode = preset_mode
        elif preset_mode in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._speed = None
            self._percentage = None
            self._preset_mode = None
        else:
            _LOGGER.error(
                "Received invalid preset_mode: %s. Expected: %s",
                preset_mode,
                self.preset_mode,
            )
            self._speed = None
            self._percentage = None
            self._preset_mode = None

    @callback
    def _update_oscillating(self, oscillating):
        # Validate osc
        if oscillating == "True" or oscillating is True:
            self._oscillating = True
        elif oscillating == "False" or oscillating is False:
            self._oscillating = False
        elif oscillating in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._oscillating = None
        else:
            _LOGGER.error(
                "Received invalid oscillating: %s. Expected: True/False", oscillating
            )
            self._oscillating = None

    @callback
    def _update_direction(self, direction):
        # Validate direction
        if direction in _VALID_DIRECTIONS:
            self._direction = direction
        elif direction in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._direction = None
        else:
            _LOGGER.error(
                "Received invalid direction: %s. Expected: %s",
                direction,
                ", ".join(_VALID_DIRECTIONS),
            )
            self._direction = None
