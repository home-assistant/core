"""Sensor for the City of Montreal's Planif-Neige snow removal APIs."""

from datetime import datetime
import logging

from homeassistant.components.planifneige import (
    CONF_STREETID, DATA_PLANIFNEIGE, PLANIFNEIGE_ATTRIBUTION)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.restore_state import RestoreEntity

DEPENDENCIES = ['planifneige']

_LOGGER = logging.getLogger(__name__)

DB_TIMEFORMAT = '%Y-%m-%d %H:%M:%S'

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
        self._name = sensor[CONF_NAME]
        self._street_id = sensor[CONF_STREETID]
        self._icon = ""
        self._start_plan_date = None
        self._end_plan_date = None
        self._start_replan_date = None
        self._end_replan_date = None
        self._date_updated = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def street_id(self):
        """Return the street_id of the sensor."""
        return self._street_id

    @property
    def start_plan_date(self):
        """Return the start planned date of the sensor."""
        return self.format_dbtime(self._start_plan_date)

    @property
    def end_plan_date(self):
        """Return the end planned date of the sensor."""
        return self.format_dbtime(self._end_plan_date)

    @property
    def start_replan_date(self):
        """Return the start replanned date of the sensor."""
        return self.format_dbtime(self._start_replan_date)

    @property
    def end_replan_date(self):
        """Return the end replanned date of the sensor."""
        return self.format_dbtime(self._end_replan_date)

    @property
    def date_updated(self):
        """Return the date updated of the sensor."""
        return self.format_dbtime(self._date_updated)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        for street in self._data:
            if street[1] == self._street_id:
                self._state = STREET_STATE[str(street[2])][0]
                self._icon = STREET_STATE[str(street[2])][1]
                self._start_plan_date = street[3]
                self._end_plan_date = street[4]
                self._start_replan_date = street[5]
                self._end_replan_date = street[6]
                self._date_updated = street[7]

    def format_dbtime(self, db_timestamp):
        """Return DB timestamp format in ISO8601 format"""
        if db_timestamp is None:
            return None
        else:
            return datetime.strptime(db_timestamp, DB_TIMEFORMAT)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'street_side_id': self.street_id,
            'start_plan_date': self.start_plan_date,
            'end_plan_date': self.end_plan_date,
            'start_replan_date': self.start_replan_date,
            'end_replan_date': self.end_replan_date,
            'date_updated': self.date_updated,
            ATTR_ATTRIBUTION: PLANIFNEIGE_ATTRIBUTION
        }

    @property
    def icon(self):
        """Return the icon."""
        return self._icon
