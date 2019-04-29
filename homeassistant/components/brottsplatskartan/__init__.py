"""Component for Brottsplatskartan information."""
import uuid

import voluptuous as vol

from homeassistant.const import (ATTR_ATTRIBUTION, CONF_LATITUDE,
                                 CONF_LONGITUDE, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (_LOGGER, ATTR_INCIDENTS, CONF_AREA, CONF_SENSOR,
                    DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN,
                    SIGNAL_UPDATE_BPK)

AREAS = [
    "Blekinge län", "Dalarnas län", "Gotlands län", "Gävleborgs län",
    "Hallands län", "Jämtlands län", "Jönköpings län", "Kalmar län",
    "Kronobergs län", "Norrbottens län", "Skåne län", "Stockholms län",
    "Södermanlands län", "Uppsala län", "Värmlands län", "Västerbottens län",
    "Västernorrlands län", "Västmanlands län", "Västra Götalands län",
    "Örebro län", "Östergötlands län"
]

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
            vol.Optional(CONF_AREA, default=[]):
            vol.All(cv.ensure_list, [vol.In(AREAS)]),
            vol.Optional(CONF_SENSOR):
            cv.boolean,
        })
    },
    extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Brottsplatskartan platform."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    area = conf.get(CONF_AREA)
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    name = conf.get(CONF_NAME)

    # Every Home Assistant instance should have their own unique
    # app parameter: https://brottsplatskartan.se/sida/api
    app = 'ha-{}'.format(uuid.getnode())

    import brottsplatskartan

    hass.data[DOMAIN] = {}
    bpk = brottsplatskartan.BrottsplatsKartan(app=app,
                                              area=area,
                                              latitude=latitude,
                                              longitude=longitude)
    incidents = bpk.get_incidents()

    hass.data[DOMAIN][CONF_NAME] = name
    hass.data[DOMAIN][ATTR_ATTRIBUTION] = brottsplatskartan.ATTRIBUTION
    hass.data[DOMAIN][ATTR_INCIDENTS] = []
    hass.data[DOMAIN][ATTR_INCIDENTS] = incidents

    def hub_refresh(event_time):
        """Call Brottsplatskartan API to refresh information."""
        incidents = bpk.get_incidents()
        if len(incidents) != len(hass.data[DOMAIN][ATTR_INCIDENTS]):
            _LOGGER.debug("Updating Brottsplatskartan data")
            hass.data[DOMAIN][ATTR_INCIDENTS].clear()
            hass.data[DOMAIN][ATTR_INCIDENTS].extend(incidents)
            async_dispatcher_send(hass, SIGNAL_UPDATE_BPK)

    if conf.get(CONF_SENSOR):
        hass.helpers.discovery.load_platform(CONF_SENSOR, DOMAIN, {}, config)

    # Call the Brottsplatskartan API to refresh updates.
    async_track_time_interval(hass, hub_refresh, DEFAULT_SCAN_INTERVAL)

    return True
