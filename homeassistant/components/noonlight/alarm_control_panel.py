"""Support for Noonlight alarm control panels."""
from homeassistant.components.unifi.const import CONF_POE_CLIENTS
from homeassistant import config_entries
import logging
from noonlight_homeassistant import noonlight

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT,
    FORMAT_NUMBER,
    PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
)

from homeassistant.const import CONF_API_TOKEN, CONF_ADDRESS, CONF_PIN

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from .const import (
    CONF_CITY,
    CONF_INSTRUCTIONS,
    CONF_PHONE,
    CONF_ZIPCODE,
    CONF_ADDRESS_NAME,
    _LOGGER,
    DATA_NOONLIGHT_CONFIG,
    DOMAIN,
    ATTR_NOONLIGHT_ALARM_ID,
    CONF_SERVICES,
)

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

CONF_NAME = "Noonlight Alarm"
CONF_UNIQUE_ID = "001122334455"
CONF_ARM_AWAY_ACTION = "arm_away"
CONF_ARM_HOME_ACTION = "arm_home"
CONF_ARM_NIGHT_ACTION = "arm_night"
CONF_DISARM_ACTION = "disarm"
CONF_ALARM_CONTROL_PANELS = "panels"
CONF_CODE_ARM_REQUIRED = "code_arm_required"


async def _async_create_entities(hass, config):
    """Create Noonlight Alarm Control Panel."""
    alarm_control_panels = []

    name = CONF_NAME
    disarm_action = CONF_DISARM_ACTION
    arm_away_action = CONF_ARM_AWAY_ACTION
    arm_home_action = CONF_ARM_HOME_ACTION
    arm_night_action = CONF_ARM_NIGHT_ACTION
    code_arm_required = CONF_CODE_ARM_REQUIRED
    unique_id = CONF_UNIQUE_ID

    alarm_control_panels.append(
        AlarmControlPanelNoonlight(
            hass,
            name,
            disarm_action,
            arm_away_action,
            arm_home_action,
            arm_night_action,
            code_arm_required,
            unique_id,
        )
    )

    return alarm_control_panels


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Noonlight Alarm Control Panels."""
    async_add_entities(await _async_create_entities(hass, config))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up then noonlight alarm panel."""

    data = hass.data[DOMAIN]
    alarmControlPanel = AlarmControlPanelNoonlight(
        config_entry,
        hass,
        CONF_NAME,
        CONF_DISARM_ACTION,
        CONF_ARM_AWAY_ACTION,
        CONF_ARM_HOME_ACTION,
        CONF_ARM_HOME_ACTION,
        CONF_CODE_ARM_REQUIRED,
        CONF_UNIQUE_ID,
    )

    devices = [alarmControlPanel]
    # print(data.apiToken)

    async_add_entities(devices, True)


class AlarmControlPanelNoonlight(AlarmControlPanelEntity):
    """Representation of a Noonlight Alarm Control Panel."""

    def __init__(
        self,
        config_entry,
        hass,
        name,
        disarm_action,
        arm_away_action,
        arm_home_action,
        arm_night_action,
        code_arm_required,
        unique_id,
    ):

        api_token = config_entry.data[CONF_API_TOKEN]
        self.address_name = config_entry.data[CONF_ADDRESS_NAME]
        self.address = config_entry.data[CONF_ADDRESS]
        self.address_city = config_entry.data[CONF_CITY]
        self.address_state = config_entry.data[CONF_STATE]
        self.address_zipcode = config_entry.data[CONF_ZIPCODE]
        self.services = config_entry.data[CONF_SERVICES]
        self.police = self.services.find("Police") != -1
        self.fire = self.services.find("Fire") != -1
        self.medical = self.services.find("Medical") != -1
        self.other = self.services.find("Other") != -1
        self.instructions = config_entry.data[CONF_INSTRUCTIONS]
        self.phone = config_entry.data[CONF_PHONE]
        self.pin = config_entry.data[CONF_PIN]
        code_arm_required = False

        self.alarm = noonlight.Noonlight(
            "https://api-sandbox.noonlight.com/dispatch/v1/alarms",
            # "https://api.noonlight.com/dispatch/v1/alarms",
            api_token,
        )

        """Initialize the panel."""
        super().__init__()
        # self.entity_id = async_generate_entity_id(
        #   ENTITY_ID_FORMAT, device_id, hass=hass
        # )
        self.entity_id = "alarm_control_panel.noonlight"
        self._name = "Noonlight"
        self._disarm_script = None
        self._code_arm_required = code_arm_required
        self._state = STATE_ALARM_DISARMED
        self._unique_id = (
            config_entry.data[CONF_API_TOKEN]
            + self.services
            + config_entry.data[CONF_PHONE]
            + config_entry.data[CONF_ADDRESS_NAME]
        )
        self.noonlight_alarm_id = None
        self.noonlight_alarm_status = None
        self.noonlight_alarm_owner_id = None
        self.noonlight_alarm_created_at = None

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
        # return STATE_ALARM_DISARMED

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        supported_features = 0
        supported_features = supported_features | SUPPORT_ALARM_ARM_NIGHT
        supported_features = supported_features | SUPPORT_ALARM_ARM_HOME
        supported_features = supported_features | SUPPORT_ALARM_ARM_AWAY
        supported_features = supported_features | SUPPORT_ALARM_TRIGGER

        return supported_features

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""

        return {
            "noonlight_alarm_id": self.noonlight_alarm_id,
            "noonlight_alarm_status": self.noonlight_alarm_status,
            "noonlight_alarm_owner_id": self.noonlight_alarm_owner_id,
            "noonlight_alarm_created_at": self.noonlight_alarm_created_at,
        }

    @callback
    def _update_state(self, result):
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
        await super().async_added_to_hass()

    async def _async_alarm_arm(self, state, script=None, code=None):
        """Arm the panel to specified state."""
        optimistic_set = False
        self._state = state

        if optimistic_set:
            self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Arm the panel to Away."""
        self._state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_arm_home(self, code=None):
        """Arm the panel to Home."""
        self._state = STATE_ALARM_ARMED_HOME

    async def async_alarm_arm_night(self, code=None):
        """Arm the panel to Night."""
        self._state = STATE_ALARM_ARMED_NIGHT

    async def async_alarm_disarm(self, code=None):
        """Disarm the panel."""
        await self.hass.async_add_executor_job(self.cancel_alarm)

        self._state = STATE_ALARM_DISARMED

    def cancel_alarm(self) -> None:
        response = self.alarm.updateAlarm(self.noonlight_alarm_id)

        if response:
            self.noonlight_alarm_id = None
            self.noonlight_alarm_status = "Canceled"

    def trigger_alarm(self) -> None:

        response = self.alarm.createAlarm(
            self.address,
            self.address_city,
            self.address_state,
            self.address_zipcode,
            self.police,
            self.fire,
            self.medical,
            self.other,
            self.instructions,
            self.address_name,
            self.phone,
            self.pin,
        )

        if response != False:
            self.noonlight_alarm_id = response["id"]
            self.noonlight_alarm_status = response["status"]
            self.noonlight_alarm_owner_id = response["owner_id"]
            self.noonlight_alarm_created_at = response["created_at"]
        else:
            return False

    async def async_alarm_trigger(self, code=None):
        """trigger the alarm."""
        await self.hass.async_add_executor_job(self.trigger_alarm)
        self._state = STATE_ALARM_TRIGGERED
