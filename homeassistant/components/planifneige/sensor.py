"""Sensor for the City of Montreal's Planif-Neige snow removal APIs."""

import logging

from homeassistant.components.planifneige import (
    DATA_PLANIFNEIGE, PLANIFNEIGE_ATTRIBUTION)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.restore_state import RestoreEntity

DEPENDENCIES = ['planifneige']

_LOGGER = logging.getLogger(__name__)

CONF_STREETID = 'streetid'
CONF_STREETS = 'streets'
CONF_DBPATH = 'database_path'

ATTR_SENSOR = 'sensor'
ATTR_STATES = 'states'

DOMAIN = 'planifneige'

STREET_STATE = {
    '0': ['Snowed', 'mdi:snowflake'],  # street is snowed in
    '1': ['Clear', 'mdi:road'],  # street is clear
    '2': ['Planned', 'mdi:clock-outline'],  # street is planned for clearing
    '3': ['Replanned', 'mdi:clock-alert-outline'],  # clearing date replanned
    '4': ['Snowed', 'mdi:snowflake'],  # to be planned, still snowed in
    '5': ['Clearing', 'mdi:bulldozer'],  # trucks loading, still clearing
    '10': ['Ploughed', 'mdi:road']  # street cleared, snow not loaded
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the PlanifNeige platform."""
    data = hass.data[DATA_PLANIFNEIGE]
    async_add_entities(
        [PlanifNeigeSensor(data, sensor) for sensor in discovery_info]
    )


class PlanifNeigeSensor(RestoreEntity):
    """PlanifNeige sensor."""

    def __init__(self, data, sensor):
        """Initialize the sensor."""
        self._data = data.data
        self._state = None
        self._name = sensor['name']
        self._streetid = sensor['streetid']
        self._icon = ""
        self._start_plan_date = None
        self.__end_plan_date = None
        self._start_replan_date = None
        self._end_replan_date = None
        self._date_updated = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def streetid(self):
        """Return the name of the sensor."""
        return self._streetid

    @property
    def start_plan_date(self):
        """Return the name of the sensor."""
        return self._start_plan_date

    @property
    def _end_plan_date(self):
        """Return the name of the sensor."""
        return self.__end_plan_date

    @property
    def start_replan_date(self):
        """Return the name of the sensor."""
        return self._start_replan_date

    @property
    def end_replan_date(self):
        """Return the name of the sensor."""
        return self._end_replan_date

    @property
    def date_updated(self):
        """Return the name of the sensor."""
        return self._date_updated

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        for street in self._data:
            if street[1] == self._streetid:
                self._state = STREET_STATE[str(street[2])][0]
                self._icon = STREET_STATE[str(street[2])][1]
                self._start_plan_date = street[3]
                self.__end_plan_date = street[4]
                self._start_replan_date = street[5]
                self._end_replan_date = street[6]
                self._date_updated = street[7]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'start_plan_date': self._start_plan_date,
            'end_plan_date': self.__end_plan_date,
            'start_replan_date': self._start_replan_date,
            'end_replan_date': self._end_replan_date,
            'date_updated': self._date_updated,
            ATTR_ATTRIBUTION: PLANIFNEIGE_ATTRIBUTION
        }

    @property
    def icon(self):
        """Return the icon."""
        return self._icon
