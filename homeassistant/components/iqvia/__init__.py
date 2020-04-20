"""Support for IQVIA."""
import asyncio
from datetime import timedelta
import logging

from pyiqvia import Client
from pyiqvia.errors import InvalidZipError, IQVIAError
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

API_CATEGORY_MAPPING = {
    TYPE_ALLERGY_TODAY: TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_TOMORROW: TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_TOMORROW: TYPE_ALLERGY_INDEX,
    TYPE_ASTHMA_TODAY: TYPE_ASTHMA_INDEX,
    TYPE_ASTHMA_TOMORROW: TYPE_ALLERGY_INDEX,
    TYPE_DISEASE_TODAY: TYPE_DISEASE_INDEX,
}

DATA_CONFIG = "config"

DEFAULT_ATTRIBUTION = "Data provided by IQVIA™"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

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


@callback
def async_get_api_category(sensor_type):
    """Return the API category that a particular sensor type should use."""
    return API_CATEGORY_MAPPING.get(sensor_type, sensor_type)


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

    iqvia = IQVIAData(hass, Client(config_entry.data[CONF_ZIP_CODE], websession))

    try:
        await iqvia.async_update()
    except InvalidZipError:
        _LOGGER.error("Invalid ZIP code provided: %s", config_entry.data[CONF_ZIP_CODE])
        return False

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = iqvia

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
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

    def __init__(self, hass, client):
        """Initialize."""
        self._async_cancel_time_interval_listener = None
        self._client = client
        self._hass = hass
        self.data = {}
        self.zip_code = client.zip_code

        self._api_coros = {
            TYPE_ALLERGY_FORECAST: client.allergens.extended,
            TYPE_ALLERGY_INDEX: client.allergens.current,
            TYPE_ALLERGY_OUTLOOK: client.allergens.outlook,
            TYPE_ASTHMA_FORECAST: client.asthma.extended,
            TYPE_ASTHMA_INDEX: client.asthma.current,
            TYPE_DISEASE_FORECAST: client.disease.extended,
            TYPE_DISEASE_INDEX: client.disease.current,
        }
        self._api_category_count = {
            TYPE_ALLERGY_FORECAST: 0,
            TYPE_ALLERGY_INDEX: 0,
            TYPE_ALLERGY_OUTLOOK: 0,
            TYPE_ASTHMA_FORECAST: 0,
            TYPE_ASTHMA_INDEX: 0,
            TYPE_DISEASE_FORECAST: 0,
            TYPE_DISEASE_INDEX: 0,
        }
        self._api_category_locks = {
            TYPE_ALLERGY_FORECAST: asyncio.Lock(),
            TYPE_ALLERGY_INDEX: asyncio.Lock(),
            TYPE_ALLERGY_OUTLOOK: asyncio.Lock(),
            TYPE_ASTHMA_FORECAST: asyncio.Lock(),
            TYPE_ASTHMA_INDEX: asyncio.Lock(),
            TYPE_DISEASE_FORECAST: asyncio.Lock(),
            TYPE_DISEASE_INDEX: asyncio.Lock(),
        }

    async def _async_get_data_from_api(self, api_category):
        """Update and save data for a particular API category."""
        if self._api_category_count[api_category] == 0:
            return

        try:
            self.data[api_category] = await self._api_coros[api_category]()
        except IQVIAError as err:
            _LOGGER.error("Unable to get %s data: %s", api_category, err)
            self.data[api_category] = None

    async def _async_update_listener_action(self, now):
        """Define an async_track_time_interval action to update data."""
        await self.async_update()

    @callback
    def async_deregister_api_interest(self, sensor_type):
        """Decrement the number of entities with data needs from an API category."""
        # If this deregistration should leave us with no registration at all, remove the
        # time interval:
        if sum(self._api_category_count.values()) == 0:
            if self._async_cancel_time_interval_listener:
                self._async_cancel_time_interval_listener()
                self._async_cancel_time_interval_listener = None
            return

        api_category = async_get_api_category(sensor_type)
        self._api_category_count[api_category] -= 1

    async def async_register_api_interest(self, sensor_type):
        """Increment the number of entities with data needs from an API category."""
        # If this is the first registration we have, start a time interval:
        if not self._async_cancel_time_interval_listener:
            self._async_cancel_time_interval_listener = async_track_time_interval(
                self._hass, self._async_update_listener_action, DEFAULT_SCAN_INTERVAL,
            )

        api_category = async_get_api_category(sensor_type)
        self._api_category_count[api_category] += 1

        # If a sensor registers interest in a particular API call and the data doesn't
        # exist for it yet, make the API call and grab the data:
        async with self._api_category_locks[api_category]:
            if api_category not in self.data:
                await self._async_get_data_from_api(api_category)

    async def async_update(self):
        """Update IQVIA data."""
        tasks = [
            self._async_get_data_from_api(api_category)
            for api_category in self._api_coros
        ]

        await asyncio.gather(*tasks)

        _LOGGER.debug("Received new data")
        async_dispatcher_send(self._hass, TOPIC_DATA_UPDATE)


class IQVIAEntity(Entity):
    """Define a base IQVIA entity."""

    def __init__(self, iqvia, sensor_type, name, icon, zip_code):
        """Initialize the sensor."""
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
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_DATA_UPDATE, update)
        )

        await self._iqvia.async_register_api_interest(self._type)
        if self._type == TYPE_ALLERGY_FORECAST:
            # Entities that express interest in allergy forecast data should also
            # express interest in allergy outlook data:
            await self._iqvia.async_register_api_interest(TYPE_ALLERGY_OUTLOOK)

        self.update_from_latest_data()

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        self._iqvia.async_deregister_api_interest(self._type)
        if self._type == TYPE_ALLERGY_FORECAST:
            # Entities that lose interest in allergy forecast data should also lose
            # interest in allergy outlook data:
            self._iqvia.async_deregister_api_interest(TYPE_ALLERGY_OUTLOOK)

    @callback
    def update_from_latest_data(self):
        """Update the entity's state."""
        raise NotImplementedError()
