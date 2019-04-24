"""Support for IQVIA."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL)
from homeassistant.core import callback
from homeassistant.helpers import (
    aiohttp_client, config_validation as cv, discovery)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DATA_CLIENT, DATA_LISTENER, DOMAIN, SENSORS, TOPIC_DATA_UPDATE,
    TYPE_ALLERGY_FORECAST, TYPE_ALLERGY_HISTORIC, TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK, TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
    TYPE_ALLERGY_YESTERDAY, TYPE_ASTHMA_FORECAST, TYPE_ASTHMA_HISTORIC,
    TYPE_ASTHMA_INDEX, TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
    TYPE_ASTHMA_YESTERDAY, TYPE_DISEASE_FORECAST)

_LOGGER = logging.getLogger(__name__)

CONF_ZIP_CODE = 'zip_code'

DATA_CONFIG = 'config'

DEFAULT_ATTRIBUTION = 'Data provided by IQVIA™'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

NOTIFICATION_ID = 'iqvia_setup'
NOTIFICATION_TITLE = 'IQVIA Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ZIP_CODE): str,
        vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
            vol.All(cv.ensure_list, [vol.In(SENSORS)])
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the IQVIA component."""
    from pyiqvia import Client
    from pyiqvia.errors import IQVIAError

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        iqvia = IQVIAData(
            Client(conf[CONF_ZIP_CODE], websession),
            conf[CONF_MONITORED_CONDITIONS])
        await iqvia.async_update()
    except IQVIAError as err:
        _LOGGER.error('Unable to set up IQVIA: %s', err)
        hass.components.persistent_notification.create(
            'Error: {0}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    hass.data[DOMAIN][DATA_CLIENT] = iqvia

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, conf)

    async def refresh(event_time):
        """Refresh IQVIA data."""
        _LOGGER.debug('Updating IQVIA data')
        await iqvia.async_update()
        async_dispatcher_send(hass, TOPIC_DATA_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER] = async_track_time_interval(
        hass, refresh,
        timedelta(
            seconds=conf.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.seconds)))

    return True


class IQVIAData:
    """Define a data object to retrieve info from IQVIA."""

    def __init__(self, client, sensor_types):
        """Initialize."""
        self._client = client
        self.data = {}
        self.sensor_types = sensor_types
        self.zip_code = client.zip_code

    async def _get_data(self, method, key):
        """Return API data from a specific call."""
        from pyiqvia.errors import IQVIAError

        try:
            data = await method()
            self.data[key] = data
        except IQVIAError as err:
            _LOGGER.error('Unable to get "%s" data: %s', key, err)
            self.data[key] = {}

    async def async_update(self):
        """Update IQVIA data."""
        from pyiqvia.errors import InvalidZipError

        # IQVIA sites require a bit more complicated error handling, given that
        # it sometimes has parts (but not the whole thing) go down:
        #
        # 1. If `InvalidZipError` is thrown, quit everything immediately.
        # 2. If an individual request throws any other error, try the others.
        try:
            if TYPE_ALLERGY_FORECAST in self.sensor_types:
                await self._get_data(
                    self._client.allergens.extended, TYPE_ALLERGY_FORECAST)
                await self._get_data(
                    self._client.allergens.outlook, TYPE_ALLERGY_OUTLOOK)

            if TYPE_ALLERGY_HISTORIC in self.sensor_types:
                await self._get_data(
                    self._client.allergens.historic, TYPE_ALLERGY_HISTORIC)

            if any(s in self.sensor_types
                   for s in [TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                             TYPE_ALLERGY_YESTERDAY]):
                await self._get_data(
                    self._client.allergens.current, TYPE_ALLERGY_INDEX)

            if TYPE_ASTHMA_FORECAST in self.sensor_types:
                await self._get_data(
                    self._client.asthma.extended, TYPE_ASTHMA_FORECAST)

            if TYPE_ASTHMA_HISTORIC in self.sensor_types:
                await self._get_data(
                    self._client.asthma.historic, TYPE_ASTHMA_HISTORIC)

            if any(s in self.sensor_types
                   for s in [TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                             TYPE_ASTHMA_YESTERDAY]):
                await self._get_data(
                    self._client.asthma.current, TYPE_ASTHMA_INDEX)

            if TYPE_DISEASE_FORECAST in self.sensor_types:
                await self._get_data(
                    self._client.disease.extended, TYPE_DISEASE_FORECAST)

            _LOGGER.debug("New data retrieved: %s", self.data)
        except InvalidZipError:
            _LOGGER.error(
                "Cannot retrieve data for ZIP code: %s", self._client.zip_code)
            self.data = {}


class IQVIAEntity(Entity):
    """Define a base IQVIA entity."""

    def __init__(self, iqvia, kind, name, icon, zip_code):
        """Initialize the sensor."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._iqvia = iqvia
        self._kind = kind
        self._name = name
        self._state = None
        self._zip_code = zip_code

    @property
    def available(self):
        """Return True if entity is available."""
        if self._kind in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW,
                          TYPE_ALLERGY_YESTERDAY):
            return self._iqvia.data.get(TYPE_ALLERGY_INDEX) is not None

        if self._kind in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW,
                          TYPE_ASTHMA_YESTERDAY):
            return self._iqvia.data.get(TYPE_ASTHMA_INDEX) is not None

        return self._iqvia.data.get(self._kind) is not None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}'.format(self._zip_code, self._kind)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return 'index'

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_DATA_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
