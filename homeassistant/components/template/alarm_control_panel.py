"""Support for Template alarm control panels."""
from enum import Enum
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT,
    FORMAT_NUMBER,
    FORMAT_TEXT,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    ATTR_CODE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from .const import DOMAIN
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
]

CONF_ARM_AWAY_ACTION = "arm_away"
CONF_ARM_HOME_ACTION = "arm_home"
CONF_ARM_NIGHT_ACTION = "arm_night"
CONF_DISARM_ACTION = "disarm"
CONF_ALARM_CONTROL_PANELS = "panels"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_FORMAT = "code_format"


class CodeFormat(Enum):
    """Class to represent different code formats."""

    no_code = None
    number = FORMAT_NUMBER
    text = FORMAT_TEXT


ALARM_CONTROL_PANEL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_DISARM_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_AWAY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_HOME_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_ARM_NIGHT_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_FORMAT, default=CodeFormat.number.name): cv.enum(
            CodeFormat
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ALARM_CONTROL_PANELS): cv.schema_with_slug_keys(
            ALARM_CONTROL_PANEL_SCHEMA
        ),
    }
)


async def _async_create_entities(hass, config):
    """Create Template Alarm Control Panels."""
    alarm_control_panels = []

    for device, device_config in config[CONF_ALARM_CONTROL_PANELS].items():
        name = device_config.get(CONF_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        disarm_action = device_config.get(CONF_DISARM_ACTION)
        arm_away_action = device_config.get(CONF_ARM_AWAY_ACTION)
        arm_home_action = device_config.get(CONF_ARM_HOME_ACTION)
        arm_night_action = device_config.get(CONF_ARM_NIGHT_ACTION)
        code_arm_required = device_config[CONF_CODE_ARM_REQUIRED]
        code_format = device_config[CONF_CODE_FORMAT]
        unique_id = device_config.get(CONF_UNIQUE_ID)

        alarm_control_panels.append(
            AlarmControlPanelTemplate(
                hass,
                device,
                name,
                state_template,
                disarm_action,
                arm_away_action,
                arm_home_action,
                arm_night_action,
                code_arm_required,
                code_format,
                unique_id,
            )
        )

    return alarm_control_panels


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template Alarm Control Panels."""
    async_add_entities(await _async_create_entities(hass, config))


class AlarmControlPanelTemplate(TemplateEntity, AlarmControlPanelEntity):
    """Representation of a templated Alarm Control Panel."""

    def __init__(
        self,
        hass,
        device_id,
        name,
        state_template,
        disarm_action,
        arm_away_action,
        arm_home_action,
        arm_night_action,
        code_arm_required,
        code_format,
        unique_id,
    ):
        """Initialize the panel."""
        super().__init__()
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = name
        self._template = state_template
        self._disarm_script = None
        self._code_arm_required = code_arm_required
        self._code_format = code_format
        if disarm_action is not None:
            self._disarm_script = Script(hass, disarm_action, name, DOMAIN)
        self._arm_away_script = None
        if arm_away_action is not None:
            self._arm_away_script = Script(hass, arm_away_action, name, DOMAIN)
        self._arm_home_script = None
        if arm_home_action is not None:
            self._arm_home_script = Script(hass, arm_home_action, name, DOMAIN)
        self._arm_night_script = None
        if arm_night_action is not None:
            self._arm_night_script = Script(hass, arm_night_action, name, DOMAIN)

        self._state = None
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the display name of this alarm control panel."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this alarm control panel."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        supported_features = 0
        if self._arm_night_script is not None:
            supported_features = supported_features | SUPPORT_ALARM_ARM_NIGHT

        if self._arm_home_script is not None:
            supported_features = supported_features | SUPPORT_ALARM_ARM_HOME

        if self._arm_away_script is not None:
            supported_features = supported_features | SUPPORT_ALARM_ARM_AWAY

        return supported_features

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return self._code_format.value

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    @callback
    def _update_state(self, result):
        if isinstance(result, TemplateError):
            self._state = None
            return

        # Validate state
        if result in _VALID_STATES:
            self._state = result
            _LOGGER.debug("Valid state - %s", result)
            return

        _LOGGER.error(
            "Received invalid alarm panel state: %s. Expected: %s",
            result,
            ", ".join(_VALID_STATES),
        )
        self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        if self._template:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        await super().async_added_to_hass()

    async def _async_alarm_arm(self, state, script=None, code=None):
        """Arm the panel to specified state with supplied script."""
        optimistic_set = False

        if self._template is None:
            self._state = state
            optimistic_set = True

        if script is not None:
            await script.async_run({ATTR_CODE: code}, context=self._context)
        else:
            _LOGGER.error("No script action defined for %s", state)

        if optimistic_set:
            self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Arm the panel to Away."""
        await self._async_alarm_arm(
            STATE_ALARM_ARMED_AWAY, script=self._arm_away_script, code=code
        )

    async def async_alarm_arm_home(self, code=None):
        """Arm the panel to Home."""
        await self._async_alarm_arm(
            STATE_ALARM_ARMED_HOME, script=self._arm_home_script, code=code
        )

    async def async_alarm_arm_night(self, code=None):
        """Arm the panel to Night."""
        await self._async_alarm_arm(
            STATE_ALARM_ARMED_NIGHT, script=self._arm_night_script, code=code
        )

    async def async_alarm_disarm(self, code=None):
        """Disarm the panel."""
        await self._async_alarm_arm(
            STATE_ALARM_DISARMED, script=self._disarm_script, code=code
        )
