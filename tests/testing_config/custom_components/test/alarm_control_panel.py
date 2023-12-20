"""Provide a mock alarm_control_panel platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            "arm_code": MockAlarm(
                name="Alarm arm code",
                code_arm_required=True,
                unique_id="unique_arm_code",
            ),
            "no_arm_code": MockAlarm(
                name="Alarm no arm code",
                code_arm_required=False,
                unique_id="unique_no_arm_code",
            ),
        }
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockAlarm(MockEntity, AlarmControlPanelEntity):
    """Mock Alarm control panel class."""

    def __init__(self, **values):
        """Init the Mock Alarm Control Panel."""
        self._state = None

        MockEntity.__init__(self, **values)

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._handle("code_arm_required")

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        return (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.TRIGGER
            | AlarmControlPanelEntityFeature.ARM_VACATION
        )

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._state = STATE_ALARM_ARMED_AWAY
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._state = STATE_ALARM_ARMED_HOME
        self.schedule_update_ha_state()

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._state = STATE_ALARM_ARMED_NIGHT
        self.schedule_update_ha_state()

    def alarm_arm_vacation(self, code=None):
        """Send arm night command."""
        self._state = STATE_ALARM_ARMED_VACATION
        self.schedule_update_ha_state()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code == "1234":
            self._state = STATE_ALARM_DISARMED
            self.schedule_update_ha_state()

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        self._state = STATE_ALARM_TRIGGERED
        self.schedule_update_ha_state()
