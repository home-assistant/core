"""Platform for the City of Montreal's Planif-Neige snow removal APIs."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_SCAN_INTERVAL, CONF_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL_INVALIDATION_VERSION)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

DOMAIN = 'planifneige'
DATA_PLANIFNEIGE = 'data_planifneige'

DATA_UPDATED = '{}_data_updated'.format(DOMAIN)

PLANIFNEIGE_ATTRIBUTION = "Information provided by the City of Montreal "

REQUIREMENTS = ['planif-neige-client==0.0.5']

_LOGGER = logging.getLogger(__name__)

CONF_STREETID = 'streetid'
CONF_STREETS = 'streets'
CONF_DBPATH = 'database_path'

ATTR_SENSOR = 'sensor'
ATTR_STATES = 'states'

DEFAULT_INTERVAL = timedelta(minutes=5)

_STREET_SCHEME = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_STREETID): cv.positive_int
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        vol.Schema({
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL):
                vol.All(cv.time_period, cv.positive_timedelta),
            vol.Required(CONF_DBPATH): cv.string,
            vol.Required(CONF_STREETS): [_STREET_SCHEME]
        }),
        cv.deprecated(
            CONF_UPDATE_INTERVAL,
            replacement_key=CONF_SCAN_INTERVAL,
            invalidation_version=CONF_UPDATE_INTERVAL_INVALIDATION_VERSION,
            default=DEFAULT_INTERVAL
        )
    )
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the PlanifNeige component."""
    conf = config[DOMAIN]
    data = hass.data[DATA_PLANIFNEIGE] = PlanifNeigeData(hass, conf.get(CONF_API_KEY),
                                               conf.get(CONF_DBPATH),
                                               conf.get(CONF_STREETS))

    async_track_time_interval(
        hass, data.update, conf[CONF_SCAN_INTERVAL]
        )

    def update(call=None):
        """Service call to manually update the data."""
        data.update()

    hass.services.async_register(DOMAIN, 'planifneige', update)

    hass.async_create_task(
        async_load_platform(
            hass,
            SENSOR_DOMAIN,
            DOMAIN,
            conf[CONF_STREETS],
            config
        )
    )

    return True


class PlanifNeigeData:
    """Get the latest data from PlanifNeige."""

    def __init__(self, hass, api_key, db_path, streets):
        """Initialize the data object."""
        self.data = []
        self._hass = hass
        self._streets = streets
        self._api_key = api_key
        self._db_path = db_path

    def update(self, now=None):
        """Get the latest data from PlanifNeige."""
        from planif_neige_client import PlanifNeigeClient
        _pn = PlanifNeigeClient.PlanifNeigeClient(self._api_key,
                                                  self._db_path)
        _pn.get_planification_for_date()

        for street in self._streets:
            self.data.append(
                _pn.get_planification_for_street(street['streetid']))

        dispatcher_send(self._hass, DATA_UPDATED)
