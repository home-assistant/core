"""Support for Template alarm control panels."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT, FORMAT_NUMBER, AlarmControlPanel)
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ENTITY_ID, CONF_FRIENDLY_NAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED,
    STATE_ALARM_ARMED_NIGHT, EVENT_HOMEASSISTANT_START, MATCH_ALL, ATTR_CODE
)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
                 STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED,
                 STATE_ALARM_ARMED_NIGHT]

CONF_ARM_AWAY_ACTION = 'arm_away'
CONF_ARM_HOME_ACTION = 'arm_home'
CONF_ARM_NIGHT_ACTION = 'arm_night'
CONF_DISARM_ACTION = 'disarm'
CONF_ALARM_CONTROL_PANELS = 'panels'
CONF_CODE_ARM_REQUIRED = 'code_arm_required'

ALARM_CONTROL_PANEL_SCHEMA = vol.Schema({
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ALARM_CONTROL_PANELS):
        cv.schema_with_slug_keys(ALARM_CONTROL_PANEL_SCHEMA),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Template Alarm Control Panels."""
    alarm_control_panels = []

    for device, device_config in config[CONF_ALARM_CONTROL_PANELS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        disarm_action = device_config.get(CONF_DISARM_ACTION)
        arm_away_action = device_config.get(CONF_ARM_AWAY_ACTION)
        arm_home_action = device_config.get(CONF_ARM_HOME_ACTION)
        arm_night_action = device_config.get(CONF_ARM_NIGHT_ACTION)
        code_arm_required = device_config.get(CONF_CODE_ARM_REQUIRED)

        template_entity_ids = set()

        if state_template is not None:
            temp_ids = state_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)
        else:
            _LOGGER.warning("No value template - will use optimistic state")

        if icon_template is not None:
            temp_ids = icon_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if entity_picture_template is not None:
            temp_ids = entity_picture_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if not template_entity_ids:
            template_entity_ids = MATCH_ALL

        entity_ids = device_config.get(CONF_ENTITY_ID, template_entity_ids)

        alarm_control_panels.append(
            AlarmControlPanelTemplate(
                hass, device, friendly_name, state_template,
                icon_template, entity_picture_template, disarm_action,
                arm_away_action, arm_home_action, arm_night_action,
                code_arm_required, entity_ids)
        )

    if not alarm_control_panels:
        _LOGGER.error("No alarm control panels added")
        return False

    async_add_entities(alarm_control_panels)
    return True


class AlarmControlPanelTemplate(AlarmControlPanel):
    """Representation of a templated Alarm Control Panel."""

    def __init__(self, hass, device_id, friendly_name, state_template,
                 icon_template, entity_picture_template, disarm_action,
                 arm_away_action, arm_home_action, arm_night_action,
                 code_arm_required, entity_ids):
        """Initialize the panel."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._disarm_script = None
        self._code_arm_required = code_arm_required
        if disarm_action is not None:
            self._disarm_script = Script(hass, disarm_action)
        self._arm_away_script = None
        if arm_away_action is not None:
            self._arm_away_script = Script(hass, arm_away_action)
        self._arm_home_script = None
        if arm_home_action is not None:
            self._arm_home_script = Script(hass, arm_home_action)
        self._arm_night_script = None
        if arm_night_action is not None:
            self._arm_night_script = Script(hass, arm_night_action)

        self._state = None
        self._icon = None
        self._entity_picture = None
        self._brightness = None
        self._entities = entity_ids

        if self._template is not None:
            self._template.hass = self.hass
        if self._icon_template is not None:
            self._icon_template.hass = self.hass
        if self._entity_picture_template is not None:
            self._entity_picture_template.hass = self.hass

    @property
    def name(self):
        """Return the display name of this alarm control panel."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_alarm_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_alarm_control_panel_startup(event):
            """Update template on startup."""
            if self._template is not None:
                async_track_state_change(
                    self.hass, self._entities, template_alarm_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_alarm_control_panel_startup)

    async def async_alarm_arm_away(self, code=None):
        """Arm the panel to Away."""
        optimistic_set = False

        if self._template is None:
            _LOGGER.info("Optimistically setting arm state to Away")
            self._state = STATE_ALARM_ARMED_AWAY
            optimistic_set = True

        if self._arm_away_script is not None:
            await self._arm_away_script.async_run({
                ATTR_CODE: code
            }, context=self._context)
        else:
            _LOGGER.warning("No script action defined for Arm Away.")

        if optimistic_set:
            self.async_schedule_update_ha_state()

    async def async_alarm_arm_home(self, code=None):
        """Arm the panel to Home."""
        optimistic_set = False

        if self._template is None:
            _LOGGER.info("Optimistically setting arm state to Home")
            self._state = STATE_ALARM_ARMED_HOME
            optimistic_set = True

        if self._arm_home_script is not None:
            await self._arm_home_script.async_run({
                ATTR_CODE: code
            }, context=self._context)
        else:
            _LOGGER.warning("No script action defined for Arm Home.")

        if optimistic_set:
            self.async_schedule_update_ha_state()

    async def async_alarm_arm_night(self, code=None):
        """Arm the panel to Night."""
        optimistic_set = False

        if self._template is None:
            _LOGGER.info("Optimistically setting arm state to Night")
            self._state = STATE_ALARM_ARMED_NIGHT
            optimistic_set = True

        if self._arm_night_script is not None:
            await self._arm_night_script.async_run({
                ATTR_CODE: code
            }, context=self._context)
        else:
            _LOGGER.warning("No script action defined for Arm Night.")

        if optimistic_set:
            self.async_schedule_update_ha_state()

    async def async_alarm_disarm(self, code=None):
        """Disarm the panel."""
        optimistic_set = False

        if self._template is None:
            _LOGGER.info("Optimistically setting arm state to Disarmed")
            self._state = STATE_ALARM_DISARMED
            optimistic_set = True

        if self._disarm_script is not None:
            await self._disarm_script.async_run({
                ATTR_CODE: code
            }, context=self._context)
        else:
            _LOGGER.warning("No script action defined for Disarm.")

        if optimistic_set:
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Update the state from the template."""
        if self._template is not None:
            try:
                state = self._template.async_render().lower()
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._state = None

            if state in _VALID_STATES:
                self._state = state
            else:
                _LOGGER.error(
                    'Received invalid alarm panel state: %s. Expected: %s',
                    state, ', '.join(_VALID_STATES))
                self._state = None

        for property_name, template in (
                ('_icon', self._icon_template),
                ('_entity_picture', self._entity_picture_template)):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._name)
                    return

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._name, ex)
