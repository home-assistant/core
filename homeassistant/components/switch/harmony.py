#####SWITCH####
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT
import homeassistant.components.harmony as harmony
import pyharmony
import logging


REQUIREMENTS = ['pyharmony>=0.2.0']
_LOGGER = logging.getLogger(__name__)
CONF_IP = 'ip'


def setup_platform(hass, config, add_devices_callback, configData, discovery_info=None):
    for hub in harmony.HUB_CONF_GLOBAL:
        activities = pyharmony.ha_get_activities(hub[CONF_USERNAME], hub[CONF_PASSWORD], hub[CONF_IP], hub[CONF_PORT])
        for activity in activities:
            add_devices_callback([HarmonySwitch(activity,
                                                hub['name'],
                                                hub['username'],
                                                hub['password'],
                                                hub['ip'],
                                                hub['port'],
                                                False,
                                                activities[activity])])
    return True


class HarmonySwitch(harmony.HarmonyDevice, SwitchDevice):
    """Switch used to start an activity via a Harmony device"""

    def __init__(self, activityName, hubName, username, password, ip, port, state, activityID):
        super().__init__(activityName, username, password, ip, port)
        self._name = 'harmony_' + hubName + '_' + self._name
        self._state = state
        self._activityID = activityID

    @property
    def name(self):
        """Return the name of the activity"""
        return self._name

    @property
    def activityID(self):
        return self._activityID

    @property
    def is_on(self):
        return self._state

    def turn_on(self):
        pyharmony.ha_start_activity(self._email, self._password, self._ip, self._port, self._activityID)
        self._state = False
