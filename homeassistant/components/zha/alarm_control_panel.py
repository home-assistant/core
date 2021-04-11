"""Alarm control panels on Zigbee Home Automation networks."""
import functools
import logging
from typing import Any

from zigpy.zcl.clusters.security import IasAce

from homeassistant.components.alarm_control_panel import (
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    ATTR_CODE_FORMAT,
    DOMAIN,
    FORMAT_TEXT,
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
    AlarmControlPanelEntity,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import discovery
from .core.channels.security import (
    SIGNAL_ALARM_TRIGGERED,
    SIGNAL_ARMED_STATE_CHANGED,
    IasAce as AceChannel,
)
from .core.const import (
    CHANNEL_IAS_ACE,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)


STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)

IAS_ACE_STATE_MAP = {
    IasAce.PanelStatus.Panel_Disarmed: STATE_ALARM_DISARMED,
    IasAce.PanelStatus.Armed_Stay: STATE_ALARM_ARMED_HOME,
    IasAce.PanelStatus.Armed_Night: STATE_ALARM_ARMED_NIGHT,
    IasAce.PanelStatus.Armed_Away: STATE_ALARM_ARMED_AWAY,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation alarm control panel from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


@STRICT_MATCH(channel_names=CHANNEL_IAS_ACE)
class ZHAAlarmControlPanel(ZhaEntity, AlarmControlPanelEntity):
    """Entity for ZHA alarm control devices."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA alarm control device."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel: AceChannel = channels[0]
        self._channel.panel_code = "1234"
        self._channel.code_required_arm_actions = False
        self._state = STATE_ALARM_DISARMED

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._channel, SIGNAL_ARMED_STATE_CHANGED, self.async_set_armed_mode
        )
        self.async_accept_signal(
            self._channel, SIGNAL_ALARM_TRIGGERED, self.async_alarm_trigger
        )

    @callback
    def async_set_armed_mode(self, value: Any) -> None:
        """Set the entity state."""
        _LOGGER.debug("armed state [%s]", value)
        self._state = IAS_ACE_STATE_MAP.get(value)
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        super().async_restore_last_state(last_state)

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return FORMAT_TEXT

    @property
    def changed_by(self):
        """Last change triggered by."""
        return None

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._channel.code_required_arm_actions

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        success = self._channel.arm(IasAce.ArmMode.Disarm, code, 0)
        if not success:
            return
        self._state = STATE_ALARM_DISARMED
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        success = self._channel.arm(IasAce.ArmMode.Arm_Day_Home_Only, code, 0)
        if not success:
            return
        self._state = STATE_ALARM_ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        success = self._channel.arm(IasAce.ArmMode.Arm_All_Zones, code, 0)
        if not success:
            return
        self._state = STATE_ALARM_ARMED_AWAY
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        success = self._channel.arm(IasAce.ArmMode.Arm_Night_Sleep_Only, code, 0)
        if not success:
            return
        self._state = STATE_ALARM_ARMED_NIGHT
        self.async_write_ha_state()

    async def async_alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        self._state = STATE_ALARM_TRIGGERED
        self.async_write_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_TRIGGER
        )

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by,
            ATTR_CODE_ARM_REQUIRED: self.code_arm_required,
        }
        return state_attr
