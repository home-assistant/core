"""Support for IQVIA."""
import asyncio
from datetime import timedelta
import logging

from pyiqvia import Client
from pyiqvia.errors import InvalidZipError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.decorator import Registry

from .config_flow import configured_instances
from .const import (
    CONF_ZIP_CODE,
    DATA_CLIENT,
    DATA_LISTENER,
    DOMAIN,
    SENSORS,
    TOPIC_DATA_UPDATE,
    TYPE_ALLERGY_FORECAST,
    TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK,
    TYPE_ALLERGY_TODAY,
    TYPE_ALLERGY_TOMORROW,
    TYPE_ASTHMA_FORECAST,
    TYPE_ASTHMA_INDEX,
    TYPE_ASTHMA_TODAY,
    TYPE_ASTHMA_TOMORROW,
    TYPE_DISEASE_FORECAST,
    TYPE_DISEASE_INDEX,
    TYPE_DISEASE_TODAY,
)

_LOGGER = logging.getLogger(__name__)

DATA_CONFIG = "config"

DEFAULT_ATTRIBUTION = "Data provided by IQVIA™"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

FETCHER_MAPPING = {
    (TYPE_ALLERGY_FORECAST,): (TYPE_ALLERGY_FORECAST, TYPE_ALLERGY_OUTLOOK),
    (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW): (TYPE_ALLERGY_INDEX,),
    (TYPE_ASTHMA_FORECAST,): (TYPE_ASTHMA_FORECAST,),
    (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW): (TYPE_ASTHMA_INDEX,),
    (TYPE_DISEASE_FORECAST,): (TYPE_DISEASE_FORECAST,),
    (TYPE_DISEASE_TODAY,): (TYPE_DISEASE_INDEX,),
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_MONITORED_CONDITIONS, invalidation_version="0.114.0"),
            vol.Schema(
                {
                    vol.Required(CONF_ZIP_CODE): str,
                    vol.Optional(
                        CONF_MONITORED_CONDITIONS, default=list(SENSORS)
                    ): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the IQVIA component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_ZIP_CODE] in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up IQVIA as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        iqvia = IQVIAData(Client(config_entry.data[CONF_ZIP_CODE], websession))
        await iqvia.async_update()
    except InvalidZipError:
        _LOGGER.error("Invalid ZIP code provided: %s", config_entry.data[CONF_ZIP_CODE])
        return False

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = iqvia

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    async def refresh(event_time):
        """Refresh IQVIA data."""
        _LOGGER.debug("Updating IQVIA data")
        await iqvia.async_update()
        async_dispatcher_send(hass, TOPIC_DATA_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    remove_listener()

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    return True


class IQVIAData:
    """Define a data object to retrieve info from IQVIA."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.data = {}
        self.zip_code = client.zip_code

        self.fetchers = Registry()
        self.fetchers.register(TYPE_ALLERGY_FORECAST)(self._client.allergens.extended)
        self.fetchers.register(TYPE_ALLERGY_OUTLOOK)(self._client.allergens.outlook)
        self.fetchers.register(TYPE_ALLERGY_INDEX)(self._client.allergens.current)
        self.fetchers.register(TYPE_ASTHMA_FORECAST)(self._client.asthma.extended)
        self.fetchers.register(TYPE_ASTHMA_INDEX)(self._client.asthma.current)
        self.fetchers.register(TYPE_DISEASE_FORECAST)(self._client.disease.extended)
        self.fetchers.register(TYPE_DISEASE_INDEX)(self._client.disease.current)

    async def async_update(self):
        """Update IQVIA data."""
        tasks = {}

        for conditions, fetcher_types in FETCHER_MAPPING.items():
            if not any(c in SENSORS for c in conditions):
                continue

            for fetcher_type in fetcher_types:
                tasks[fetcher_type] = self.fetchers[fetcher_type]()

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for key, result in zip(tasks, results):
            if isinstance(result, Exception):
                _LOGGER.error("Unable to get %s data: %s", key, result)
                self.data[key] = {}
                continue

            _LOGGER.debug("Loaded new %s data", key)
            self.data[key] = result


class IQVIAEntity(Entity):
    """Define a base IQVIA entity."""

    def __init__(self, iqvia, sensor_type, name, icon, zip_code):
        """Initialize the sensor."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._iqvia = iqvia
        self._name = name
        self._state = None
        self._type = sensor_type
        self._zip_code = zip_code

    @property
    def available(self):
        """Return True if entity is available."""
        if self._type in (TYPE_ALLERGY_TODAY, TYPE_ALLERGY_TOMORROW):
            return self._iqvia.data.get(TYPE_ALLERGY_INDEX) is not None

        if self._type in (TYPE_ASTHMA_TODAY, TYPE_ASTHMA_TOMORROW):
            return self._iqvia.data.get(TYPE_ASTHMA_INDEX) is not None

        if self._type == TYPE_DISEASE_TODAY:
            return self._iqvia.data.get(TYPE_DISEASE_INDEX) is not None

        return self._iqvia.data.get(self._type) is not None

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
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._zip_code}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "index"

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_DATA_UPDATE, update
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
