"""Support for Arlo Alarm Control Panels."""
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ATTRIBUTION, DATA_ARLO, SIGNAL_UPDATE_ARLO

_LOGGER = logging.getLogger(__name__)

ARMED = "armed"

CONF_HOME_MODE_NAME = "home_mode_name"
CONF_AWAY_MODE_NAME = "away_mode_name"
CONF_NIGHT_MODE_NAME = "night_mode_name"

DISARMED = "disarmed"

ICON = "mdi:security"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOME_MODE_NAME, default=ARMED): cv.string,
        vol.Optional(CONF_AWAY_MODE_NAME, default=ARMED): cv.string,
        vol.Optional(CONF_NIGHT_MODE_NAME, default=ARMED): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Arlo Alarm Control Panels."""
    arlo = hass.data[DATA_ARLO]

    if not arlo.base_stations:
        return

    home_mode_name = config[CONF_HOME_MODE_NAME]
    away_mode_name = config[CONF_AWAY_MODE_NAME]
    night_mode_name = config[CONF_NIGHT_MODE_NAME]
    base_stations = []
    for base_station in arlo.base_stations:
        base_stations.append(
            ArloBaseStation(
                base_station, home_mode_name, away_mode_name, night_mode_name
            )
        )
    add_entities(base_stations, True)


class ArloBaseStation(AlarmControlPanelEntity):
    """Representation of an Arlo Alarm Control Panel."""

    def __init__(self, data, home_mode_name, away_mode_name, night_mode_name):
        """Initialize the alarm control panel."""
        self._base_station = data
        self._home_mode_name = home_mode_name
        self._away_mode_name = away_mode_name
        self._night_mode_name = night_mode_name
        self._state = None

    @property
    def icon(self):
        """Return icon."""
        return ICON

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ARLO, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating Arlo Alarm Control Panel %s", self.name)
        mode = self._base_station.mode
        if mode:
            self._state = self._get_state_from_mode(mode)
        else:
            self._state = None

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._base_station.mode = DISARMED

    def alarm_arm_away(self, code=None):
        """Send arm away command. Uses custom mode."""
        self._base_station.mode = self._away_mode_name

    def alarm_arm_home(self, code=None):
        """Send arm home command. Uses custom mode."""
        self._base_station.mode = self._home_mode_name

    def alarm_arm_night(self, code=None):
        """Send arm night command. Uses custom mode."""
        self._base_station.mode = self._night_mode_name

    @property
    def name(self):
        """Return the name of the base station."""
        return self._base_station.name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._base_station.device_id,
        }

    def _get_state_from_mode(self, mode):
        """Convert Arlo mode to Home Assistant state."""
        if mode == ARMED:
            return STATE_ALARM_ARMED_AWAY
        if mode == DISARMED:
            return STATE_ALARM_DISARMED
        if mode == self._home_mode_name:
            return STATE_ALARM_ARMED_HOME
        if mode == self._away_mode_name:
            return STATE_ALARM_ARMED_AWAY
        if mode == self._night_mode_name:
            return STATE_ALARM_ARMED_NIGHT
        return mode
