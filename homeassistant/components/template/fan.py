"""Support for Template fans."""
import logging

import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    ENTITY_ID_FORMAT,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
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

from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)

CONF_FANS = "fans"
CONF_SPEED_LIST = "speeds"
CONF_SPEED_TEMPLATE = "speed_template"
CONF_OSCILLATING_TEMPLATE = "oscillating_template"
CONF_DIRECTION_TEMPLATE = "direction_template"
CONF_ON_ACTION = "turn_on"
CONF_OFF_ACTION = "turn_off"
CONF_SET_SPEED_ACTION = "set_speed"
CONF_SET_OSCILLATING_ACTION = "set_oscillating"
CONF_SET_DIRECTION_ACTION = "set_direction"

_VALID_STATES = [STATE_ON, STATE_OFF]
_VALID_OSC = [True, False]
_VALID_DIRECTIONS = [DIRECTION_FORWARD, DIRECTION_REVERSE]

FAN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SPEED_TEMPLATE): cv.template,
        vol.Optional(CONF_OSCILLATING_TEMPLATE): cv.template,
        vol.Optional(CONF_DIRECTION_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_SPEED_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_OSCILLATING_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_DIRECTION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(
            CONF_SPEED_LIST, default=[SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
        ): cv.ensure_list,
        vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_FANS): cv.schema_with_slug_keys(FAN_SCHEMA)}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template Fans."""
    fans = []

    for device, device_config in config[CONF_FANS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config[CONF_VALUE_TEMPLATE]
        speed_template = device_config.get(CONF_SPEED_TEMPLATE)
        oscillating_template = device_config.get(CONF_OSCILLATING_TEMPLATE)
        direction_template = device_config.get(CONF_DIRECTION_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)

        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]
        set_speed_action = device_config.get(CONF_SET_SPEED_ACTION)
        set_oscillating_action = device_config.get(CONF_SET_OSCILLATING_ACTION)
        set_direction_action = device_config.get(CONF_SET_DIRECTION_ACTION)

        speed_list = device_config[CONF_SPEED_LIST]
        unique_id = device_config.get(CONF_UNIQUE_ID)

        fans.append(
            TemplateFan(
                hass,
                device,
                friendly_name,
                state_template,
                speed_template,
                oscillating_template,
                direction_template,
                availability_template,
                on_action,
                off_action,
                set_speed_action,
                set_oscillating_action,
                set_direction_action,
                speed_list,
                unique_id,
            )
        )

    async_add_entities(fans)


class TemplateFan(TemplateEntity, FanEntity):
    """A template fan component."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        speed_template,
        oscillating_template,
        direction_template,
        availability_template,
        on_action,
        off_action,
        set_speed_action,
        set_oscillating_action,
        set_direction_action,
        speed_list,
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
        self._oscillating = None
        self._direction = None

        if self._speed_template:
            self._supported_features |= SUPPORT_SET_SPEED
        if self._oscillating_template:
            self._supported_features |= SUPPORT_OSCILLATE
        if self._direction_template:
            self._supported_features |= SUPPORT_DIRECTION

        self._unique_id = unique_id

        # List of valid speeds
        self._speed_list = speed_list

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
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillating

    @property
    def current_direction(self):
        """Return the oscillation state."""
        return self._direction

    # pylint: disable=arguments-differ
    async def async_turn_on(self, speed: str = None) -> None:
        """Turn on the fan."""
        await self._on_script.async_run({ATTR_SPEED: speed}, context=self._context)
        self._state = STATE_ON

        if speed is not None:
            await self.async_set_speed(speed)

    # pylint: disable=arguments-differ
    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        await self._off_script.async_run(context=self._context)
        self._state = STATE_OFF

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self._set_speed_script is None:
            return

        if speed in self._speed_list:
            self._speed = speed
            await self._set_speed_script.async_run(
                {ATTR_SPEED: speed}, context=self._context
            )
        else:
            _LOGGER.error(
                "Received invalid speed: %s. Expected: %s", speed, self._speed_list
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
        if speed in self._speed_list:
            self._speed = speed
        elif speed in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._speed = None
        else:
            _LOGGER.error(
                "Received invalid speed: %s. Expected: %s", speed, self._speed_list
            )
            self._speed = None

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
                "Received invalid oscillating: %s. Expected: True/False", oscillating,
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
