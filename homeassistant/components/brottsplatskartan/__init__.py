"""Component for Brottsplatskartan information."""
import uuid

import voluptuous as vol

from homeassistant.const import (ATTR_ATTRIBUTION, CONF_LATITUDE,
                                 CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
                                 CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import slugify

from .const import (_LOGGER, ATTR_INCIDENTS, CONF_AREAS, CONF_SENSOR,
                    DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN, SENSOR_TYPES,
                    SIGNAL_UPDATE_BPK)

AREAS = [
    "Blekinge län", "Dalarnas län", "Gotlands län", "Gävleborgs län",
    "Hallands län", "Jämtlands län", "Jönköpings län", "Kalmar län",
    "Kronobergs län", "Norrbottens län", "Skåne län", "Stockholms län",
    "Södermanlands län", "Uppsala län", "Värmlands län", "Västerbottens län",
    "Västernorrlands län", "Västmanlands län", "Västra Götalands län",
    "Örebro län", "Östergötlands län"
]

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
    vol.All(cv.ensure_list, vol.Unique(), [vol.In(SENSOR_TYPES)])
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Inclusive(CONF_LATITUDE, 'coordinates'):
            cv.latitude,
            vol.Inclusive(CONF_LONGITUDE, 'coordinates'):
            cv.longitude,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME):
            cv.string,
            vol.Optional(CONF_AREAS, default=[]):
            vol.All(cv.ensure_list, [vol.In(AREAS)]),
            vol.Optional(CONF_SENSOR, default={}):
            SENSOR_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Brottsplatskartan platform."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    areas = conf.get(CONF_AREAS)
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    name = conf.get(CONF_NAME)

    # Every Home Assistant instance should have their own unique
    # app parameter: https://brottsplatskartan.se/sida/api
    app = 'ha-{}'.format(uuid.getnode())

    import brottsplatskartan

    hass.data[DOMAIN] = {}
    bpk = brottsplatskartan.BrottsplatsKartan(app=app,
                                              areas=areas,
                                              latitude=latitude,
                                              longitude=longitude)
    incidents = bpk.get_incidents()

    hass.data[DOMAIN][CONF_NAME] = name
    hass.data[DOMAIN][ATTR_ATTRIBUTION] = brottsplatskartan.ATTRIBUTION
    hass.data[DOMAIN][ATTR_INCIDENTS] = incidents

    def hub_refresh(event_time):
        """Call Brottsplatskartan API to refresh information."""
        incidents = bpk.get_incidents()
        if not incidents:
            return False
        for incident_area in incidents:
            slugify_incident_area = slugify(incident_area)
            incident_area_update_signal = "{}_{}".format(
                SIGNAL_UPDATE_BPK, slugify_incident_area)
            if len(incidents[incident_area]) != len(
                    hass.data[DOMAIN][ATTR_INCIDENTS][incident_area]):
                _LOGGER.debug("Updating Brottsplatskartan data for %s",
                              incident_area)
                hass.data[DOMAIN][ATTR_INCIDENTS][incident_area].clear()
                hass.data[DOMAIN][ATTR_INCIDENTS][incident_area].extend(
                    incidents[incident_area])
                dispatcher_send(hass, incident_area_update_signal)

    monitored_conditions = conf.get(CONF_SENSOR).get(CONF_MONITORED_CONDITIONS)
    sensor_config = {
        CONF_MONITORED_CONDITIONS: monitored_conditions,
        'name': name,
    }

    if conf.get(CONF_SENSOR):
        hass.helpers.discovery.load_platform(CONF_SENSOR, DOMAIN,
                                             sensor_config, config)

    # Call the Brottsplatskartan API to refresh updates.
    track_time_interval(hass, hub_refresh, DEFAULT_SCAN_INTERVAL)

    return True
