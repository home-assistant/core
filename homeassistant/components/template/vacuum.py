"""Support for Template vacuums."""
import logging

import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STOP,
    StateVacuumEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from . import extract_entities, initialise_templates
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = "vacuums"
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
_VALID_STATES = [
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_PAUSED,
    STATE_IDLE,
    STATE_RETURNING,
    STATE_ERROR,
]

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_SPEED_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES, default={}): vol.Schema(
            {cv.string: cv.template}
        ),
        vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_FAN_SPEED_LIST, default=[]): cv.ensure_list,
        vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_VACUUMS): vol.Schema({cv.slug: VACUUM_SCHEMA})}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template Vacuums."""
    vacuums = []

    for device, device_config in config[CONF_VACUUMS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        battery_level_template = device_config.get(CONF_BATTERY_LEVEL_TEMPLATE)
        fan_speed_template = device_config.get(CONF_FAN_SPEED_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        attribute_templates = device_config.get(CONF_ATTRIBUTE_TEMPLATES)

        start_action = device_config[SERVICE_START]
        pause_action = device_config.get(SERVICE_PAUSE)
        stop_action = device_config.get(SERVICE_STOP)
        return_to_base_action = device_config.get(SERVICE_RETURN_TO_BASE)
        clean_spot_action = device_config.get(SERVICE_CLEAN_SPOT)
        locate_action = device_config.get(SERVICE_LOCATE)
        set_fan_speed_action = device_config.get(SERVICE_SET_FAN_SPEED)

        fan_speed_list = device_config[CONF_FAN_SPEED_LIST]
        unique_id = device_config.get(CONF_UNIQUE_ID)

        templates = {
            CONF_VALUE_TEMPLATE: state_template,
            CONF_BATTERY_LEVEL_TEMPLATE: battery_level_template,
            CONF_FAN_SPEED_TEMPLATE: fan_speed_template,
            CONF_AVAILABILITY_TEMPLATE: availability_template,
        }

        initialise_templates(hass, templates, attribute_templates)
        entity_ids = extract_entities(
            device, "vacuum", None, templates, attribute_templates
        )

        vacuums.append(
            TemplateVacuum(
                hass,
                device,
                friendly_name,
                state_template,
                battery_level_template,
                fan_speed_template,
                availability_template,
                start_action,
                pause_action,
                stop_action,
                return_to_base_action,
                clean_spot_action,
                locate_action,
                set_fan_speed_action,
                fan_speed_list,
                entity_ids,
                attribute_templates,
                unique_id,
            )
        )

    async_add_entities(vacuums)


class TemplateVacuum(StateVacuumEntity):
    """A template vacuum component."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        battery_level_template,
        fan_speed_template,
        availability_template,
        start_action,
        pause_action,
        stop_action,
        return_to_base_action,
        clean_spot_action,
        locate_action,
        set_fan_speed_action,
        fan_speed_list,
        entity_ids,
        attribute_templates,
        unique_id,
    ):
        """Initialize the vacuum."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name

        self._template = state_template
        self._battery_level_template = battery_level_template
        self._fan_speed_template = fan_speed_template
        self._availability_template = availability_template
        self._supported_features = SUPPORT_START
        self._attribute_templates = attribute_templates
        self._attributes = {}

        domain = __name__.split(".")[-2]

        self._start_script = Script(hass, start_action, friendly_name, domain)

        self._pause_script = None
        if pause_action:
            self._pause_script = Script(hass, pause_action, friendly_name, domain)
            self._supported_features |= SUPPORT_PAUSE

        self._stop_script = None
        if stop_action:
            self._stop_script = Script(hass, stop_action, friendly_name, domain)
            self._supported_features |= SUPPORT_STOP

        self._return_to_base_script = None
        if return_to_base_action:
            self._return_to_base_script = Script(
                hass, return_to_base_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_RETURN_HOME

        self._clean_spot_script = None
        if clean_spot_action:
            self._clean_spot_script = Script(
                hass, clean_spot_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_CLEAN_SPOT

        self._locate_script = None
        if locate_action:
            self._locate_script = Script(hass, locate_action, friendly_name, domain)
            self._supported_features |= SUPPORT_LOCATE

        self._set_fan_speed_script = None
        if set_fan_speed_action:
            self._set_fan_speed_script = Script(
                hass, set_fan_speed_action, friendly_name, domain
            )
            self._supported_features |= SUPPORT_FAN_SPEED

        self._state = None
        self._battery_level = None
        self._fan_speed = None
        self._available = True

        if self._template:
            self._supported_features |= SUPPORT_STATE
        if self._battery_level_template:
            self._supported_features |= SUPPORT_BATTERY

        self._entities = entity_ids
        self._unique_id = unique_id

        # List of valid fan speeds
        self._fan_speed_list = fan_speed_list

    @property
    def name(self):
        """Return the display name of this vacuum."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this vacuum."""
        return self._unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._state

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list:
        """Get the list of available fan speeds."""
        return self._fan_speed_list

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_start(self):
        """Start or resume the cleaning task."""
        await self._start_script.async_run(context=self._context)

    async def async_pause(self):
        """Pause the cleaning task."""
        if self._pause_script is None:
            return

        await self._pause_script.async_run(context=self._context)

    async def async_stop(self, **kwargs):
        """Stop the cleaning task."""
        if self._stop_script is None:
            return

        await self._stop_script.async_run(context=self._context)

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self._return_to_base_script is None:
            return

        await self._return_to_base_script.async_run(context=self._context)

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self._clean_spot_script is None:
            return

        await self._clean_spot_script.async_run(context=self._context)

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        if self._locate_script is None:
            return

        await self._locate_script.async_run(context=self._context)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self._set_fan_speed_script is None:
            return

        if fan_speed in self._fan_speed_list:
            self._fan_speed = fan_speed
            await self._set_fan_speed_script.async_run(
                {ATTR_FAN_SPEED: fan_speed}, context=self._context
            )
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s. Expected: %s",
                fan_speed,
                self._fan_speed_list,
            )

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_vacuum_state_listener(event):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_vacuum_startup(event):
            """Update template on startup."""
            if self._entities != MATCH_ALL:
                # Track state changes only for valid templates
                self.hass.helpers.event.async_track_state_change_event(
                    self._entities, template_vacuum_state_listener
                )

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_vacuum_startup
        )

    async def async_update(self):
        """Update the state from the template."""
        # Update state
        if self._template is not None:
            try:
                state = self._template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                state = None
                self._state = None

            # Validate state
            if state in _VALID_STATES:
                self._state = state
            elif state == STATE_UNKNOWN:
                self._state = None
            else:
                _LOGGER.error(
                    "Received invalid vacuum state: %s. Expected: %s",
                    state,
                    ", ".join(_VALID_STATES),
                )
                self._state = None

        # Update battery level if 'battery_level_template' is configured
        if self._battery_level_template is not None:
            try:
                battery_level = self._battery_level_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                battery_level = None

            # Validate battery level
            if battery_level and 0 <= int(battery_level) <= 100:
                self._battery_level = int(battery_level)
            else:
                _LOGGER.error(
                    "Received invalid battery level: %s. Expected: 0-100", battery_level
                )
                self._battery_level = None

        # Update fan speed if 'fan_speed_template' is configured
        if self._fan_speed_template is not None:
            try:
                fan_speed = self._fan_speed_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                fan_speed = None
                self._state = None

            # Validate fan speed
            if fan_speed in self._fan_speed_list:
                self._fan_speed = fan_speed
            elif fan_speed == STATE_UNKNOWN:
                self._fan_speed = None
            else:
                _LOGGER.error(
                    "Received invalid fan speed: %s. Expected: %s",
                    fan_speed,
                    self._fan_speed_list,
                )
                self._fan_speed = None
        # Update availability if availability template is defined
        if self._availability_template is not None:
            try:
                self._available = (
                    self._availability_template.async_render().lower() == "true"
                )
            except (TemplateError, ValueError) as ex:
                _LOGGER.error(
                    "Could not render %s template %s: %s",
                    CONF_AVAILABILITY_TEMPLATE,
                    self._name,
                    ex,
                )
        # Update attribute if attribute template is defined
        if self._attribute_templates is not None:
            attrs = {}
            for key, value in self._attribute_templates.items():
                try:
                    attrs[key] = value.async_render()
                except TemplateError as err:
                    _LOGGER.error("Error rendering attribute %s: %s", key, err)

            self._attributes = attrs
