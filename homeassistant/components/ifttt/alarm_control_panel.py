"""Support for alarm control panels that can be controlled through IFTTT."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_CODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ATTR_EVENT, DOMAIN, SERVICE_PUSH_ALARM_STATE, SERVICE_TRIGGER

_LOGGER = logging.getLogger(__name__)

ALLOWED_STATES = [
    AlarmControlPanelState.DISARMED,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_HOME,
]

DATA_IFTTT_ALARM = "ifttt_alarm"
DEFAULT_NAME = "Home"

CONF_EVENT_AWAY = "event_arm_away"
CONF_EVENT_HOME = "event_arm_home"
CONF_EVENT_NIGHT = "event_arm_night"
CONF_EVENT_DISARM = "event_disarm"

DEFAULT_EVENT_AWAY = "alarm_arm_away"
DEFAULT_EVENT_HOME = "alarm_arm_home"
DEFAULT_EVENT_NIGHT = "alarm_arm_night"
DEFAULT_EVENT_DISARM = "alarm_disarm"

CONF_CODE_ARM_REQUIRED = "code_arm_required"

PLATFORM_SCHEMA = ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_EVENT_AWAY, default=DEFAULT_EVENT_AWAY): cv.string,
        vol.Optional(CONF_EVENT_HOME, default=DEFAULT_EVENT_HOME): cv.string,
        vol.Optional(CONF_EVENT_NIGHT, default=DEFAULT_EVENT_NIGHT): cv.string,
        vol.Optional(CONF_EVENT_DISARM, default=DEFAULT_EVENT_DISARM): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
    }
)

PUSH_ALARM_STATE_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_ids, vol.Required(ATTR_STATE): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a control panel managed through IFTTT."""
    if DATA_IFTTT_ALARM not in hass.data:
        hass.data[DATA_IFTTT_ALARM] = []

    name: str = config[CONF_NAME]
    code: str | None = config.get(CONF_CODE)
    code_arm_required: bool = config[CONF_CODE_ARM_REQUIRED]
    event_away: str = config[CONF_EVENT_AWAY]
    event_home: str = config[CONF_EVENT_HOME]
    event_night: str = config[CONF_EVENT_NIGHT]
    event_disarm: str = config[CONF_EVENT_DISARM]
    optimistic: bool = config[CONF_OPTIMISTIC]

    alarmpanel = IFTTTAlarmPanel(
        name,
        code,
        code_arm_required,
        event_away,
        event_home,
        event_night,
        event_disarm,
        optimistic,
    )
    hass.data[DATA_IFTTT_ALARM].append(alarmpanel)
    add_entities([alarmpanel])

    async def push_state_update(service: ServiceCall) -> None:
        """Set the service state as device state attribute."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        state = service.data.get(ATTR_STATE)
        devices = hass.data[DATA_IFTTT_ALARM]
        if entity_ids:
            devices = [d for d in devices if d.entity_id in entity_ids]

        for device in devices:
            device.push_alarm_state(state)
            device.async_schedule_update_ha_state()

    hass.services.register(
        DOMAIN,
        SERVICE_PUSH_ALARM_STATE,
        push_state_update,
        schema=PUSH_ALARM_STATE_SERVICE_SCHEMA,
    )


class IFTTTAlarmPanel(AlarmControlPanelEntity):
    """Representation of an alarm control panel controlled through IFTTT."""

    _attr_assumed_state = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self,
        name: str,
        code: str | None,
        code_arm_required: bool,
        event_away: str,
        event_home: str,
        event_night: str,
        event_disarm: str,
        optimistic: bool,
    ) -> None:
        """Initialize the alarm control panel."""
        self._attr_name = name
        self._code = code
        self._code_arm_required = code_arm_required
        self._event_away = event_away
        self._event_home = event_home
        self._event_night = event_night
        self._event_disarm = event_disarm
        self._optimistic = optimistic

    @property
    def code_format(self) -> CodeFormat | None:
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and self._code.isdigit():
            return CodeFormat.NUMBER
        return CodeFormat.TEXT

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._check_code(code):
            return
        self.set_alarm_state(self._event_disarm, AlarmControlPanelState.DISARMED)

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if self._code_arm_required and not self._check_code(code):
            return
        self.set_alarm_state(self._event_away, AlarmControlPanelState.ARMED_AWAY)

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if self._code_arm_required and not self._check_code(code):
            return
        self.set_alarm_state(self._event_home, AlarmControlPanelState.ARMED_HOME)

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        if self._code_arm_required and not self._check_code(code):
            return
        self.set_alarm_state(self._event_night, AlarmControlPanelState.ARMED_NIGHT)

    def set_alarm_state(self, event: str, state: AlarmControlPanelState) -> None:
        """Call the IFTTT trigger service to change the alarm state."""
        data = {ATTR_EVENT: event}

        self.hass.services.call(DOMAIN, SERVICE_TRIGGER, data)
        _LOGGER.debug("Called IFTTT integration to trigger event %s", event)
        if self._optimistic:
            self._attr_alarm_state = state

    def push_alarm_state(self, value: str) -> None:
        """Push the alarm state to the given value."""
        value = AlarmControlPanelState(value)
        if value in ALLOWED_STATES:
            _LOGGER.debug("Pushed the alarm state to %s", value)
            self._attr_alarm_state = value

    def _check_code(self, code: str | None) -> bool:
        return self._code is None or self._code == code
