"""
Support for the Nokia Health API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.withings/
"""
import os
import logging
import datetime
import time
from typing import List
from functools import reduce

from aiohttp import web
import voluptuous as vol

from homeassistant.core import callback, HomeAssistant, Config as HomeAssistantConfig
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import MASS_KILOGRAMS, CONF_MONITORED_CONDITIONS, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json
from homeassistant.util import Throttle, slugify

REQUIREMENTS = ['nokia==1.1.0']

_LOGGER = logging.getLogger(__name__)

WITHINGS_CONFIG_FILE = '.withings/session-{}-{}.json'
WITHINGS_AUTH_CALLBACK_PATH = '/api/withings/callback'
DATA_CONFIGURING = 'withings_configurator_clients'
SCAN_INTERVAL = datetime.timedelta(minutes=5)

SLEEP_STATE_AWAKE = 0
SLEEP_STATE_LIGHT = 1
SLEEP_STATE_DEEP = 2
SLEEP_STATE_REM = 3

MEASURE_TYPE_WEIGHT = 1
MEASURE_TYPE_FAT_MASS = 8
MEASURE_TYPE_FAT_MASS_FREE = 5
MEASURE_TYPE_MUSCLE_MASS = 76
MEASURE_TYPE_BONE_MASS = 88
MEASURE_TYPE_HEIGHT = 4
MEASURE_TYPE_TEMP = 12
MEASURE_TYPE_BODY_TEMP = 71
MEASURE_TYPE_SKIN_TEMP = 73
MEASURE_TYPE_FAT_RATIO = 6
MEASURE_TYPE_DIASTOLIC_BP = 9
MEASURE_TYPE_SYSTOLIC_BP = 10
MEASURE_TYPE_HEART_PULSE = 11
MEASURE_TYPE_SPO2 = 54
MEASURE_TYPE_HYDRATION = 77
MEASURE_TYPE_PWV = 91

MEAS_WEIGHT_KG = 'weight_kg'
MEAS_WEIGHT_LB = 'weight_lb'
MEAS_FAT_MASS_KG = 'fat_mass_kg'
MEAS_FAT_MASS_LB = 'fat_mass_lb'
MEAS_FAT_FREE_MASS_KG = 'fat_free_mass_kg'
MEAS_FAT_FREE_MASS_LB = 'fat_free_mass_lb'
MEAS_MUSCLE_MASS_KG = 'muscle_mass_kg'
MEAS_MUSCLE_MASS_LB = 'muscle_mass_lb'
MEAS_BONE_MASS_KG = 'bone_mass_kg'
MEAS_BONE_MASS_LB = 'bone_mass_lb'
MEAS_HEIGHT_M = 'height_m'
MEAS_HEIGHT_CM = 'height_cm'
MEAS_HEIGHT_IN = 'height_in'
MEAS_HEIGHT_IMP = 'height_imp'
MEAS_TEMP_C = 'temperature_c'
MEAS_TEMP_F = 'temperature_f'
MEAS_BODY_TEMP_C = 'body_temperature_c'
MEAS_BODY_TEMP_F = 'body_temperature_f'
MEAS_SKIN_TEMP_C = 'skin_temperature_c'
MEAS_SKIN_TEMP_F = 'skin_temperature_f'
MEAS_FAT_RATIO_PCT = 'fat_ratio_pct'
MEAS_DIASTOLIC_MMHG = 'diastolic_blood_pressure_mmhg'
MEAS_SYSTOLIC_MMGH = 'systolic_blood_pressure_mmhg'
MEAS_HEART_PULSE_BPM = 'heart_pulse_bpm'
MEAS_SPO2_PCT = 'spo2_pct'
MEAS_HYDRATION = 'hydration'
MEAS_PWV = 'pulse_wave_velocity'
MEAS_SLEEP_AWAKE = 'sleep_awake'
MEAS_SLEEP_LIGHT = 'sleep_light'
MEAS_SLEEP_DEEP = 'sleep_deep'
MEAS_SLEEP_REM = 'sleep_rem'
MEAS_SLEEP_TOTAL_SLEEP = 'sleep_totel_sleep'
MEAS_SLEEP_TOTAL_SESSION = 'sleep_total_session'

UOM_MASS_KG = 'kg'
UOM_MASS_LB = 'lb'
UOM_LENGTH_M = 'm'
UOM_LENGTH_CM = 'cm'
UOM_LENGTH_IN = 'in'
UOM_TEMP_C = '°C'
UOM_TEMP_F = '°F'
UOM_PCT = '%'
UOM_MMHG = 'mmhg'
UOM_BPM = 'bpm'
UOM_HOURS = 'hrs'


class WithingsAttribute(object):
    def __init__(self, measurement: str, measure_type: int, friendly_name: str, unit_of_measurement: str, icon: str) -> None:
        self.measurement = measurement
        self.measure_type = measure_type
        self.friendly_name = friendly_name
        self.unit_of_measurement = unit_of_measurement
        self.icon = icon

    def __eq__(self, that):
        return that is not None \
            and self.measurement == that.measurement \
            and self.measure_type == that.measure_type \
            and self.friendly_name == that.friendly_name \
            and self.unit_of_measurement == that.unit_of_measurement \
            and self.icon == that.icon


class WithingsMeasureAttribute(WithingsAttribute):
    def __init__(self, measurement: str, measure_type: int, friendly_name: str, unit_of_measurement: str, icon: str) -> None:
        super(WithingsMeasureAttribute, self).__init__(measurement, measure_type, friendly_name, unit_of_measurement, icon)


class WithingsSleepAttribute(WithingsAttribute):
    def __init__(self, measurement: str, friendly_name: str, unit_of_measurement: str, icon: str) -> None:
        super(WithingsSleepAttribute, self).__init__(measurement, None, friendly_name, unit_of_measurement, icon)


class WithingsDataManager(object):
    """A class representing an Withings cloud service connection."""

    def __init__(self, hass, config, add_entities, slug: str, api):
        self._hass = hass
        self._config = config
        self._add_entities = add_entities
        self._api = api
        self._slug = slug

        self._measures = None
        self._sleep = None

    def get_slug(self) -> str:
        return self._slug

    def get_api(self):
        return self._api

    def get_measures(self):
        return self._measures

    def get_sleep(self):
        return self._sleep

    @Throttle(SCAN_INTERVAL)
    async def async_refresh_token(self):
        current_time = int(time.time())
        expiration_time = int(self._api.credentials.token_expiry)

        if expiration_time - 1200 > current_time:
            _LOGGER.debug('No need to refresh access token.')
            return

        _LOGGER.debug('Refreshing access token.')
        api_client = self._api.client
        api_client.refresh_token(
            api_client.auto_refresh_url
        )

    @Throttle(SCAN_INTERVAL)
    async def async_update_measures(self) -> None:
        _LOGGER.debug('async_update_measures')

        self._measures = self._api.get_measures()

        return self._measures

    @Throttle(SCAN_INTERVAL)
    async def async_update_sleep(self) -> None:
        _LOGGER.debug('async_update_sleep')

        end_date = int(time.time())
        start_date = end_date - 86400

        self._sleep = self._api.get_sleep(
            startdate=start_date,
            enddate=end_date
        )

        return self._sleep


WITHINGS_ATTRIBUTES = [
    WithingsMeasureAttribute(MEAS_WEIGHT_KG, MEASURE_TYPE_WEIGHT, 'Weight', UOM_MASS_KG, 'mdi:weight-kilogram'),
    WithingsMeasureAttribute(MEAS_WEIGHT_LB, MEASURE_TYPE_WEIGHT, 'Weight', UOM_MASS_LB, 'mdi:weight-pound'),
    WithingsMeasureAttribute(MEAS_FAT_MASS_KG, MEASURE_TYPE_FAT_MASS, 'Fat Mass', UOM_MASS_KG, 'mdi:weight-kilogram'),
    WithingsMeasureAttribute(MEAS_FAT_MASS_LB, MEASURE_TYPE_FAT_MASS, 'Fat Mass', UOM_MASS_LB, 'mdi:weight-pound'),
    WithingsMeasureAttribute(MEAS_FAT_FREE_MASS_KG, MEASURE_TYPE_FAT_MASS_FREE, 'Fat Free Mass', UOM_MASS_KG, 'mdi:weight-kilogram'),
    WithingsMeasureAttribute(MEAS_FAT_FREE_MASS_LB, MEASURE_TYPE_FAT_MASS_FREE, 'Fat Free Mass', ';b', 'mdi:weight-pound'),
    WithingsMeasureAttribute(MEAS_MUSCLE_MASS_KG, MEASURE_TYPE_MUSCLE_MASS, 'Muscle Mass', UOM_MASS_KG, 'mdi:weight-kilogram'),
    WithingsMeasureAttribute(MEAS_MUSCLE_MASS_LB, MEASURE_TYPE_MUSCLE_MASS, 'Muscle Mass', UOM_MASS_LB, 'mdi:weight-pound'),
    WithingsMeasureAttribute(MEAS_BONE_MASS_KG, MEASURE_TYPE_BONE_MASS, 'Bone Mass', UOM_MASS_KG, 'mdi:weight-kilogram'),
    WithingsMeasureAttribute(MEAS_BONE_MASS_LB, MEASURE_TYPE_BONE_MASS, 'Bone Mass', UOM_MASS_LB, 'mdi:weight-pound'),
    
    WithingsMeasureAttribute(MEAS_HEIGHT_M, MEASURE_TYPE_HEIGHT, 'Height', UOM_LENGTH_M, 'mdi:ruler'),
    WithingsMeasureAttribute(MEAS_HEIGHT_CM, MEASURE_TYPE_HEIGHT, 'Height', UOM_LENGTH_CM, 'mdi:ruler'),
    WithingsMeasureAttribute(MEAS_HEIGHT_IN, MEASURE_TYPE_HEIGHT, 'Height', UOM_LENGTH_IN, 'mdi:ruler'),
    WithingsMeasureAttribute(MEAS_HEIGHT_IMP, MEASURE_TYPE_HEIGHT, 'Height', ' ', 'mdi:ruler'),
    
    WithingsMeasureAttribute(MEAS_TEMP_C, MEASURE_TYPE_TEMP, 'Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'),
    WithingsMeasureAttribute(MEAS_TEMP_F, MEASURE_TYPE_TEMP, 'Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'),
    WithingsMeasureAttribute(MEAS_BODY_TEMP_C, MEASURE_TYPE_BODY_TEMP, 'Body Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'),
    WithingsMeasureAttribute(MEAS_BODY_TEMP_F, MEASURE_TYPE_BODY_TEMP, 'Body Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'),
    WithingsMeasureAttribute(MEAS_SKIN_TEMP_C, MEASURE_TYPE_SKIN_TEMP, 'Skin Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'),
    WithingsMeasureAttribute(MEAS_SKIN_TEMP_F, MEASURE_TYPE_SKIN_TEMP, 'Skin Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'),
    
    WithingsMeasureAttribute(MEAS_FAT_RATIO_PCT, MEASURE_TYPE_FAT_RATIO, 'Fat Ratio', UOM_PCT, None),
    WithingsMeasureAttribute(MEAS_DIASTOLIC_MMHG, MEASURE_TYPE_DIASTOLIC_BP, 'Diastolic Blood Pressure', UOM_MMHG, None),
    WithingsMeasureAttribute(MEAS_SYSTOLIC_MMGH, MEASURE_TYPE_SYSTOLIC_BP, 'Systolic Blood Pressure', UOM_MMHG, None),
    WithingsMeasureAttribute(MEAS_HEART_PULSE_BPM, MEASURE_TYPE_HEART_PULSE, 'Heart Pulse', UOM_BPM, 'mdi:heart-pulse'),
    WithingsMeasureAttribute(MEAS_SPO2_PCT, MEASURE_TYPE_SPO2, 'SP02', UOM_PCT, None),
    WithingsMeasureAttribute(MEAS_HYDRATION, MEASURE_TYPE_HYDRATION, 'Hydration', '', 'mdi:water'),
    WithingsMeasureAttribute(MEAS_PWV, MEASURE_TYPE_PWV, 'Pulse Wave Velocity', '', None),
    
    WithingsSleepAttribute(MEAS_SLEEP_AWAKE, 'Awake', UOM_HOURS, 'mdi:sleep-off'),
    WithingsSleepAttribute(MEAS_SLEEP_LIGHT, 'Light Sleep', UOM_HOURS, 'mdi:sleep'),
    WithingsSleepAttribute(MEAS_SLEEP_DEEP, 'Deep Sleep', UOM_HOURS, 'mdi:sleep'),
    WithingsSleepAttribute(MEAS_SLEEP_REM, 'REM Sleep', UOM_HOURS, 'mdi:sleep'),
    WithingsSleepAttribute(MEAS_SLEEP_TOTAL_SLEEP, 'Total Sleep', UOM_HOURS, 'mdi:sleep'),
    WithingsSleepAttribute(MEAS_SLEEP_TOTAL_SESSION, 'Total Session', UOM_HOURS, 'mdi:sleep'),
]

CONF_SENSORS = {}
WITHINGS_MEASUREMENTS_MAP = {}
for attr in WITHINGS_ATTRIBUTES:
    CONF_SENSORS[attr.measurement] = [attr.friendly_name, attr.unit_of_measurement]
    WITHINGS_MEASUREMENTS_MAP[attr.measurement] = attr


CONF_CLIENT_ID = 'client_id'
CONF_SECRET = 'secret'
CONF_PROFILE = 'profile'
CONF_MEASUREMENTS = 'measurements'
CONF_BASE_URL = 'base_url'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Required(CONF_PROFILE): cv.string,
    vol.Optional(CONF_BASE_URL,): cv.string,
    vol.Required(CONF_MEASUREMENTS, default=[]):
        vol.All(cv.ensure_list, [vol.In(CONF_SENSORS)]),
        
    # vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        # vol.All(cv.ensure_list, [vol.In(SENSORS)])
})


def _get_credentials_from_file(hass: HomeAssistant, config_filename: str) -> nokia.NokiaCredentials:
    """Attempt to load token data from file."""
    import nokia
    _LOGGER.debug('_get_credentials_from_file')
    path = hass.config.path(config_filename)

    if not os.path.isfile(path):
        _LOGGER.debug('File does not exist: {}.'.format(path))
        return None

    _LOGGER.debug('Loading json from: {}'.format(path))
    token_data = load_json(path)
    
    _LOGGER.debug('Creating and returning nokia credentials.')
    return nokia.NokiaCredentials(
        access_token=token_data['access_token'],
        token_expiry=token_data['token_expiry'],
        token_type=token_data['token_type'],
        refresh_token=token_data['refresh_token'],
        user_id=token_data['user_id'],
        client_id=token_data['client_id'],
        consumer_secret=token_data['consumer_secret'],
    )


def _write_credentials_to_file(hass: HomeAssistant, config_filename: str, creds) -> None:
    """Attempt to store token data to file."""

    _LOGGER.debug('_write_credentials_to_file')
    path = hass.config.path(config_filename)

    _LOGGER.debug('Ensuring path to file exists. {}'.format(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    _LOGGER.debug('Getting dict from creds object.')
    token_data = creds.__dict__

    _LOGGER.debug('Saving token data to file {}.'.format(path))    
    save_json(path, token_data)


def credentials_refreshed(hass: HomeAssistant, config_filename: str, creds) -> None:
    _LOGGER.debug('async_credentials_refreshed')
    hass.add_job(_write_credentials_to_file, hass, config_filename, creds)


class WithingsConfiguring:
    request_id = None

    def __init__(self, hass, config, add_entities, slug, config_filename, oauth_initialize_callback, auth_client):
        self.hass = hass
        self.config = config
        self.add_entities = add_entities
        self.slug = slug
        self.config_filename = config_filename
        self.oauth_initialize_callback = oauth_initialize_callback
        self.auth_client = auth_client


async def async_initialize(configuring: WithingsConfiguring, creds) -> WithingsDataManager:
    """Initialize the Withings data manager object from the created session."""
    import nokia
    
    _LOGGER.debug('async_initialize')
    api = nokia.NokiaApi(
        creds, 
        refresh_cb=(lambda token: credentials_refreshed(
            configuring.hass,
            configuring.config_filename,
            api.credentials
        ))
    )
    
    _LOGGER.debug('Saving the token data..')
    credentials_refreshed(
        configuring.hass,
        configuring.config_filename,
        api.credentials
    )
    
    _LOGGER.debug('Creating withings data manager for slug: {}'.format(configuring.slug))
    data_manager = WithingsDataManager(
        configuring.hass,
        configuring.config,
        configuring.add_entities,
        configuring.slug,
        api
    )
    
    _LOGGER.debug('Attempting to refresh token.')
    await data_manager.async_refresh_token()
    
    _LOGGER.debug('Creating entities.')
    entities = []
    measurements = configuring.config.get(CONF_MEASUREMENTS)
    for measurement in measurements:
        _LOGGER.debug('Creating entity for {}'.format(measurement))
        
        attribute = WITHINGS_MEASUREMENTS_MAP[measurement]
        
        entity = WithingsHealthSensor(data_manager, attribute)

        entities.append(entity)

    _LOGGER.debug('Adding entities.')
    configuring.add_entities(entities)

    return data_manager


async def async_oauth_initialize_callback(code: str, configuring: WithingsConfiguring) -> None:
    """Call after OAuth2 response is returned."""
    _LOGGER.debug('async_oauth_initialize_callback')

    _LOGGER.debug('Requesting credentials with code: {}.'.format(code))
    creds = configuring.auth_client.get_credentials(code)

    _LOGGER.debug('Initializing data.')
    await async_initialize(configuring, creds)

    _LOGGER.debug('Finishing request.')
    configuring.hass.components.configurator.async_request_done(configuring.request_id)


async def async_setup_platform(hass: HomeAssistant, config: HomeAssistantConfig, add_entities, discovery_info=None):
    """Validate the configuration and return an withings scanner."""
    import nokia

    profile = config.get(CONF_PROFILE)
    slug = slugify(profile)
    config_filename = WITHINGS_CONFIG_FILE.format(config[CONF_CLIENT_ID], slug)
    creds = await hass.async_add_job(_get_credentials_from_file, hass, config_filename)
    callback_uri = '{}{}'.format(
        (config.get(CONF_BASE_URL) or hass.config.api.base_url).rstrip('/'),
        WITHINGS_AUTH_CALLBACK_PATH
    )

    _LOGGER.debug('Creating auth client with callback uri: {}'.format(callback_uri))
    auth_client = nokia.NokiaAuth(
        config[CONF_CLIENT_ID],
        config[CONF_SECRET],
        callback_uri,
        scope=','.join(['user.info', 'user.metrics', 'user.activity'])
    )

    configuring = WithingsConfiguring(
        hass,
        config,
        add_entities,
        slug,
        config_filename,
        async_oauth_initialize_callback,
        auth_client
    )

    if creds is not None:
        _LOGGER.debug('Token data already exists. Using that.')
        try:
            await async_initialize(configuring, creds)
            return True
        except Exception:
            _LOGGER.info('Failed to initialize. Reverting back to configure mode.', exc_info=True)

    _LOGGER.debug('Starting configuration for slug: {}'.format(slug))
    hass.http.register_view(WithingsAuthCallbackView(slug))

    configuring.request_id = hass.components.configurator.async_request_config(
        "Withings",
        description=(
            "Authorization is required to get access to Withings data. After clicking the button below, be sure to choose the profile that maps to '{}'.".format(profile)
        ),
        link_name="Click here to authorize Home Assistant.",
        link_url=auth_client.get_authorize_url(),
    )

    if DATA_CONFIGURING not in hass.data:
        hass.data[DATA_CONFIGURING] = {}

    hass.data[DATA_CONFIGURING][slug] = configuring

    return True

    
class WithingsAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    url = WITHINGS_AUTH_CALLBACK_PATH
    name = 'api:withings:callback'
    
    def __init__(self, slug: str) -> None:
        self.slug = slug

    @callback
    def get(self, request):  # pylint: disable=no-self-use
        """Finish OAuth callback request."""
        _LOGGER.debug('Received request.')
        
        hass = request.app['hass']
        params = request.query
        response = web.HTTPFound('/states')
        _LOGGER.debug('Params: {}'.format(params))

        if 'state' not in params or 'code' not in params:
            if 'error' in params:
                _LOGGER.error(
                    "Error authorizing Withings: %s", params['error'])
                return web.Response(text='ERROR_0001: Withings provided an error: {}'.format(params['error']))
            _LOGGER.error(
                "Error authorizing Withings. Invalid response returned")

            return web.Response(text='ERROR_0002: either state or code url parameters were not set.')

        if DATA_CONFIGURING not in hass.data:
            _LOGGER.error("Withings configuration request not found")
            return web.Response(text='ERROR_0003: {} was not found in hass.data. This is a bug.'.format(DATA_CONFIGURING))
            
        if self.slug not in hass.data[DATA_CONFIGURING]:
            _LOGGER.error("Withings configuration request for {} not found".format(self.slug))
            return web.Response(text='ERROR_0004: {} was not found in hass.data[{}].'.format(self.slug, DATA_CONFIGURING))

        _LOGGER.debug('Calling async_oauth_initialize_callback')
        code = params['code']
        state = params['state']
        configuring = hass.data[DATA_CONFIGURING][self.slug]
        oauth_initialize_callback = configuring.oauth_initialize_callback
        hass.async_create_task(oauth_initialize_callback(code, configuring))

        _LOGGER.debug('Returning response.')
        return response

    def __eq__(self, that):
        return that is not None \
            and isinstance(that, WithingsAuthCallbackView) \
            and self.url == that.url \
            and self.name == that.name \
            and self.slug == that.slug


class WithingsHealthSensor(Entity):
    """Implementation of a Withings sensor."""

    def __init__(self, data_manager: WithingsDataManager, attribute: WithingsAttribute) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self._attribute = attribute
        self._state = None
        
        self._slug = self._data_manager.get_slug()
        self._user_id = self._data_manager.get_api().get_credentials().user_id
        
    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'Withings {0} {1}'.format(self._attribute.measurement, self._slug)

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'withings_{0}_{1}_{2}'.format(self._slug, self._user_id, slugify(self._attribute.measurement))

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._attribute.unit_of_measurement

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._attribute.icon

    async def async_update(self) -> None:
        _LOGGER.debug('async_update slug: {}, measurement: {}, user_id: {}'.format(
            self._slug, self._attribute.measurement, self._user_id
        ))
        
        if isinstance(self._attribute, WithingsMeasureAttribute):
            _LOGGER.debug('Updating measures state.')
            await self._data_manager.async_update_measures()
            return await self.async_update_measure(self._data_manager.get_measures())
        
        elif isinstance(self._attribute, WithingsSleepAttribute):
            _LOGGER.debug('Updating sleep state.')
            await self._data_manager.async_update_sleep()
            return await self.async_update_sleep(self._data_manager.get_sleep())
   
    async def async_update_measure(self, data) -> None:
        _LOGGER.debug('async_update_measure')
        
        if data is None:
            _LOGGER.error('Provided data is None. Not updating state.')
            return
        
        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement
        
        _LOGGER.debug('Finding the unambiguous measure group with measure_type: {}.'.format(measure_type))
        measure_groups = list(filter(
            lambda g: not g.is_ambiguous() and g.get_measure(measure_type) is not None,
            data
        ))
        
        if len(measure_groups) == 0:
            _LOGGER('No measure groups found.')
            return
        
        _LOGGER.debug('Sorting list of {} measure groups by date created (DESC).'.format(len(measure_groups)))
        measure_groups.sort(key=(lambda g: g.created), reverse=True)

        _LOGGER.debug('Getting the first measure from the sorted measure groups.')
        value = measure_groups[0].get_measure(measure_type)
        
        _LOGGER.debug('Determining state for measurement: {}, measure_type: {}, unit_of_measurement: {}, value: {}'.format(
            measurement, measure_type, unit_of_measurement, value
        ))
        
        state = None
        if unit_of_measurement is UOM_MASS_KG:
            state = value
            
        elif unit_of_measurement is UOM_MASS_LB:
            state = round(value * 2.205, 2)
            
        elif unit_of_measurement is UOM_LENGTH_M:
            state = value
            
        elif unit_of_measurement is UOM_LENGTH_CM:
            state = value * 100
            
        elif unit_of_measurement is UOM_LENGTH_IN:
            state = round(value * 39.37, 2)
            
        elif unit_of_measurement is UOM_TEMP_C:
            state = value
            
        elif unit_of_measurement is UOM_TEMP_F:
            state = round((value * 1.8) + 32, 2)
            
        elif unit_of_measurement is UOM_PCT:
            state = value
            
        elif unit_of_measurement is UOM_MMHG:
            state = value
            
        elif unit_of_measurement is UOM_BPM:
            state = value

        elif measurement is MEAS_HEIGHT_IMP:
            feet_raw = value * 3.281
            feet = int(feet_raw)
            inches_ratio = feet_raw - feet
            inches = round(inches_ratio * 12, 1)
            
            state = "%d\" %d'" % (feet, inches)

        else:
            state = value
        
        _LOGGER.debug('Setting state: {}'.format(state))
        self._state = state
        
        
    async def async_update_sleep(self, data) -> None:
        _LOGGER.debug('async_update_sleep')
        
        if data is None:
            _LOGGER.error('Provided data is None. Not updating state.')
            return
        
        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement
        
        _LOGGER.debug('Building map of sleep masurements and the states to collect.')
        measurement_state_map = {
            MEAS_SLEEP_AWAKE: [SLEEP_STATE_AWAKE],
            MEAS_SLEEP_LIGHT: [SLEEP_STATE_LIGHT],
            MEAS_SLEEP_DEEP: [SLEEP_STATE_DEEP],
            MEAS_SLEEP_REM: [SLEEP_STATE_REM],
            MEAS_SLEEP_TOTAL_SLEEP: [SLEEP_STATE_LIGHT, SLEEP_STATE_DEEP, SLEEP_STATE_REM],
            MEAS_SLEEP_TOTAL_SESSION: [SLEEP_STATE_AWAKE, SLEEP_STATE_LIGHT, SLEEP_STATE_DEEP, SLEEP_STATE_REM],
        }
        
        _LOGGER.debug('Filter for series for measurement: {}.'.format(measurement))
        filtered_series = filter(
            lambda serie: serie.state in measurement_state_map[measurement],
            data.series
        )
        _LOGGER.debug('Summing timedeltas in filtered series.')
        total_time_delta = sum((serie.timedelta for serie in filtered_series), datetime.timedelta())
        
        _LOGGER.debug('Converting time to hours.')
        state_hours = round(total_time_delta.total_seconds() / 360, 1)
        
        _LOGGER.debug('Setting state: {}'.format(state_hours))
        self._state = state_hours
