"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.withings/
"""
import os
import logging
import datetime
import time

from aiohttp import web
import voluptuous as vol

from homeassistant.core import \
    callback, HomeAssistant, Config as HomeAssistantConfig
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json
from homeassistant.util import Throttle, slugify

REQUIREMENTS = ['nokia==1.2.0']
DEPENDENCIES = ['api', 'http']

_LOGGER = logging.getLogger(__name__)

WITHINGS_CONFIG_FILE = '.withings/session-{}-{}.json'
WITHINGS_AUTH_CALLBACK_PATH = '/api/withings/callback'
DATA_CONFIGURING = 'withings_configurator_clients'
SCAN_INTERVAL = datetime.timedelta(minutes=5)

STATE_AWAKE = 'awake'
STATE_LIGHT = 'light'
STATE_DEEP = 'deep'
STATE_REM = 'rem'

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
MEASURE_TYPE_SLEEP_STATE_AWAKE = 0
MEASURE_TYPE_SLEEP_STATE_LIGHT = 1
MEASURE_TYPE_SLEEP_STATE_DEEP = 2
MEASURE_TYPE_SLEEP_STATE_REM = 3
MEASURE_TYPE_SLEEP_WAKEUP_DURATION = 'wakeupduration'
MEASURE_TYPE_SLEEP_LIGHT_DURATION = 'lightsleepduration'
MEASURE_TYPE_SLEEP_DEEP_DURATION = 'deepsleepduration'
MEASURE_TYPE_SLEEP_REM_DURATION = 'remsleepduration'
MEASURE_TYPE_SLEEP_WAKUP_COUNT = 'wakeupcount'
MEASURE_TYPE_SLEEP_TOSLEEP_DURATION = 'durationtosleep'
MEASURE_TYPE_SLEEP_TOWAKEUP_DURATION = 'durationtowakeup'
MEASURE_TYPE_SLEEP_HEART_RATE_AVERAGE = 'hr_average'
MEASURE_TYPE_SLEEP_HEART_RATE_MIN = 'hr_min'
MEASURE_TYPE_SLEEP_HEART_RATE_MAX = 'hr_max'
MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_AVERAGE = 'rr_average'
MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MIN = 'rr_min'
MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MAX = 'rr_max'

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
MEAS_SLEEP_STATE = 'sleep_state'
MEAS_SLEEP_WAKEUP_DURATION_HOURS = 'wakeupduration_hours'
MEAS_SLEEP_LIGHT_DURATION_HOURS = 'lightsleepduration_hours'
MEAS_SLEEP_DEEP_DURATION_HOURS = 'deepsleepduration_hours'
MEAS_SLEEP_REM_DURATION_HOURS = 'remsleepduration_hours'
MEAS_SLEEP_WAKEUP_DURATION_MINUTES = 'wakeupduration_minutes'
MEAS_SLEEP_LIGHT_DURATION_MINUTES = 'lightsleepduration_minutes'
MEAS_SLEEP_DEEP_DURATION_MINUTES = 'deepsleepduration_minutes'
MEAS_SLEEP_REM_DURATION_MINUTES = 'remsleepduration_minutes'
MEAS_SLEEP_WAKEUP_COUNT = 'wakeupcount'
MEAS_SLEEP_TOSLEEP_DURATION_HOURS = 'durationtosleep_hours'
MEAS_SLEEP_TOWAKEUP_DURATION_HOURS = 'durationtowakeup_hours'
MEAS_SLEEP_TOSLEEP_DURATION_MINUTES = 'durationtosleep_minutes'
MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES = 'durationtowakeup_minutes'
MEAS_SLEEP_HEART_RATE_AVERAGE = 'hr_average_bpm'
MEAS_SLEEP_HEART_RATE_MIN = 'hr_min_bpm'
MEAS_SLEEP_HEART_RATE_MAX = 'hr_max_bpm'
MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE = 'rr_average_bpm'
MEAS_SLEEP_RESPIRATORY_RATE_MIN = 'rr_min_bpm'
MEAS_SLEEP_RESPIRATORY_RATE_MAX = 'rr_max_bpm'

UOM_MASS_KG = 'kg'
UOM_MASS_LB = 'lb'
UOM_LENGTH_M = 'm'
UOM_LENGTH_CM = 'cm'
UOM_LENGTH_IN = 'in'
UOM_TEMP_C = '°C'
UOM_TEMP_F = '°F'
UOM_PERCENT = '%'
UOM_MMHG = 'mmhg'
UOM_BEATS_PER_MINUTE = 'bpm'
UOM_HOURS = 'hrs'
UOM_MINUTES = 'mins'
UOM_METERS_PER_SECOND = 'm/s'
UOM_BREATHS_PER_MINUTE = 'br/m'
UOM_FREQUENCY = 'times'
UOM_IMPERIAL_HEIGHT = 'height'


class WithingsAttribute:
    """Base class for modeling withing data."""

    def __init__(self,
                 measurement: str,
                 measure_type: int,
                 friendly_name: str,
                 unit_of_measurement: str,
                 icon: str) -> None:
        """Constructor."""
        self.measurement = measurement
        self.measure_type = measure_type
        self.friendly_name = friendly_name
        self.unit_of_measurement = unit_of_measurement
        self.icon = icon

    def __eq__(self, that):
        """Compare two attributes."""
        return that is not None \
            and self.measurement == that.measurement \
            and self.measure_type == that.measure_type \
            and self.friendly_name == that.friendly_name \
            and self.unit_of_measurement == that.unit_of_measurement \
            and self.icon == that.icon


class WithingsMeasureAttribute(WithingsAttribute):
    """Model measure attributes."""


class WithingsSleepStateAttribute(WithingsAttribute):
    """Model sleep data attributes."""

    def __init__(self,
                 measurement: str,
                 friendly_name: str,
                 unit_of_measurement: str,
                 icon: str) -> None:
        """Constructor."""
        super(WithingsSleepStateAttribute, self).__init__(
            measurement,
            None,
            friendly_name,
            unit_of_measurement,
            icon
        )


class WithingsSleepSummaryAttribute(WithingsAttribute):
    """Models sleep summary attributes."""


class WithingsDataManager:
    """A class representing an Withings cloud service connection."""

    def __init__(self, slug: str, api):
        """Constructor."""
        self._api = api
        self._slug = slug

        self._measures = None
        self._sleep = None
        self._sleep_summary = None

        self.sleep_summary_last_update_parameter = None

    def get_slug(self) -> str:
        """Get the slugified profile the data is for."""
        return self._slug

    def get_api(self):
        """Get the api object."""
        return self._api

    def get_measures(self):
        """Get the current measures data."""
        return self._measures

    def get_sleep(self):
        """Get the current sleep data."""
        return self._sleep

    def get_sleep_summary(self):
        """Get the current sleep summary data."""
        return self._sleep_summary

    @Throttle(SCAN_INTERVAL)
    async def async_refresh_token(self):
        """Refresh the api token."""
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
    async def async_update_measures(self):
        """Update the measures data."""
        _LOGGER.debug('async_update_measures')

        self._measures = self._api.get_measures()

        return self._measures

    @Throttle(SCAN_INTERVAL)
    async def async_update_sleep(self):
        """Update the sleep data."""
        _LOGGER.debug('async_update_sleep')

        end_date = int(time.time())
        start_date = end_date - (6 * 60 * 60)

        self._sleep = self._api.get_sleep(
            startdate=start_date,
            enddate=end_date
        )

        return self._sleep

    @Throttle(SCAN_INTERVAL)
    async def async_update_sleep_summary(self):
        """Update the sleep summary data."""
        _LOGGER.debug('async_update_sleep_summary')

        now = datetime.datetime.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day,
            12, 0, 0, 0,
            datetime.timezone.utc
        )

        _LOGGER.debug(
            'Getting sleep summary data since: %s.',
            yesterday.strftime('%Y-%m-%d %H:%M:%S UTC')
        )

        self._sleep_summary = self._api.get_sleep_summary(
            lastupdate=yesterday_noon.timestamp()
        )

        return self._sleep_summary


WITHINGS_ATTRIBUTES = [
    WithingsMeasureAttribute(
        MEAS_WEIGHT_KG, MEASURE_TYPE_WEIGHT,
        'Weight', UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        MEAS_WEIGHT_LB, MEASURE_TYPE_WEIGHT,
        'Weight', UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        MEAS_FAT_MASS_KG, MEASURE_TYPE_FAT_MASS,
        'Fat Mass', UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        MEAS_FAT_MASS_LB, MEASURE_TYPE_FAT_MASS,
        'Fat Mass', UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        MEAS_FAT_FREE_MASS_KG, MEASURE_TYPE_FAT_MASS_FREE,
        'Fat Free Mass', UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        MEAS_FAT_FREE_MASS_LB, MEASURE_TYPE_FAT_MASS_FREE,
        'Fat Free Mass', UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        MEAS_MUSCLE_MASS_KG, MEASURE_TYPE_MUSCLE_MASS,
        'Muscle Mass', UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        MEAS_MUSCLE_MASS_LB, MEASURE_TYPE_MUSCLE_MASS,
        'Muscle Mass', UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        MEAS_BONE_MASS_KG, MEASURE_TYPE_BONE_MASS,
        'Bone Mass', UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        MEAS_BONE_MASS_LB, MEASURE_TYPE_BONE_MASS,
        'Bone Mass', UOM_MASS_LB, 'mdi:weight-pound'
    ),

    WithingsMeasureAttribute(
        MEAS_HEIGHT_M, MEASURE_TYPE_HEIGHT,
        'Height', UOM_LENGTH_M, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        MEAS_HEIGHT_CM, MEASURE_TYPE_HEIGHT,
        'Height', UOM_LENGTH_CM, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        MEAS_HEIGHT_IN, MEASURE_TYPE_HEIGHT,
        'Height', UOM_LENGTH_IN, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        MEAS_HEIGHT_IMP, MEASURE_TYPE_HEIGHT,
        'Height', UOM_IMPERIAL_HEIGHT, 'mdi:ruler'
    ),

    WithingsMeasureAttribute(
        MEAS_TEMP_C, MEASURE_TYPE_TEMP,
        'Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        MEAS_TEMP_F, MEASURE_TYPE_TEMP,
        'Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),
    WithingsMeasureAttribute(
        MEAS_BODY_TEMP_C, MEASURE_TYPE_BODY_TEMP,
        'Body Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        MEAS_BODY_TEMP_F, MEASURE_TYPE_BODY_TEMP,
        'Body Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),
    WithingsMeasureAttribute(
        MEAS_SKIN_TEMP_C, MEASURE_TYPE_SKIN_TEMP,
        'Skin Temperature', UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        MEAS_SKIN_TEMP_F, MEASURE_TYPE_SKIN_TEMP,
        'Skin Temperature', UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),

    WithingsMeasureAttribute(
        MEAS_FAT_RATIO_PCT, MEASURE_TYPE_FAT_RATIO,
        'Fat Ratio', UOM_PERCENT, None
    ),
    WithingsMeasureAttribute(
        MEAS_DIASTOLIC_MMHG, MEASURE_TYPE_DIASTOLIC_BP,
        'Diastolic Blood Pressure', UOM_MMHG, None
    ),
    WithingsMeasureAttribute(
        MEAS_SYSTOLIC_MMGH, MEASURE_TYPE_SYSTOLIC_BP,
        'Systolic Blood Pressure', UOM_MMHG, None
    ),
    WithingsMeasureAttribute(
        MEAS_HEART_PULSE_BPM, MEASURE_TYPE_HEART_PULSE,
        'Heart Pulse', UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsMeasureAttribute(
        MEAS_SPO2_PCT, MEASURE_TYPE_SPO2,
        'SP02', UOM_PERCENT, None
    ),
    WithingsMeasureAttribute(
        MEAS_HYDRATION, MEASURE_TYPE_HYDRATION,
        'Hydration', '', 'mdi:water'
    ),
    WithingsMeasureAttribute(
        MEAS_PWV, MEASURE_TYPE_PWV,
        'Pulse Wave Velocity', UOM_METERS_PER_SECOND, None
    ),

    WithingsSleepStateAttribute(MEAS_SLEEP_STATE, 'Sleep state', ' ', None),

    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_WAKEUP_DURATION_HOURS, MEASURE_TYPE_SLEEP_WAKEUP_DURATION,
        'Wakeup time', UOM_HOURS, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_LIGHT_DURATION_HOURS, MEASURE_TYPE_SLEEP_LIGHT_DURATION,
        'Light sleep', UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_DEEP_DURATION_HOURS, MEASURE_TYPE_SLEEP_DEEP_DURATION,
        'Deep sleep', UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_REM_DURATION_HOURS, MEASURE_TYPE_SLEEP_REM_DURATION,
        'REM sleep', UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_WAKEUP_DURATION_MINUTES, MEASURE_TYPE_SLEEP_WAKEUP_DURATION,
        'Wakeup time', UOM_MINUTES, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_LIGHT_DURATION_MINUTES, MEASURE_TYPE_SLEEP_LIGHT_DURATION,
        'Light sleep', UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_DEEP_DURATION_MINUTES, MEASURE_TYPE_SLEEP_DEEP_DURATION,
        'Deep sleep', UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_REM_DURATION_MINUTES, MEASURE_TYPE_SLEEP_REM_DURATION,
        'REM sleep', UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_WAKEUP_COUNT, MEASURE_TYPE_SLEEP_WAKUP_COUNT,
        'Wakeup count', UOM_FREQUENCY, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_TOSLEEP_DURATION_HOURS, MEASURE_TYPE_SLEEP_TOSLEEP_DURATION,
        'Time to sleep', UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_TOWAKEUP_DURATION_HOURS,
        MEASURE_TYPE_SLEEP_TOWAKEUP_DURATION,
        'Time to wakeup', UOM_HOURS, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_TOSLEEP_DURATION_MINUTES,
        MEASURE_TYPE_SLEEP_TOSLEEP_DURATION,
        'Time to sleep', UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES,
        MEASURE_TYPE_SLEEP_TOWAKEUP_DURATION,
        'Time to wakeup', UOM_MINUTES, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_HEART_RATE_AVERAGE, MEASURE_TYPE_SLEEP_HEART_RATE_AVERAGE,
        'Average heart rate', UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_HEART_RATE_MIN, MEASURE_TYPE_SLEEP_HEART_RATE_MIN,
        'Minimum heart rate', UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_HEART_RATE_MAX, MEASURE_TYPE_SLEEP_HEART_RATE_MAX,
        'Maximum heart rate', UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE,
        MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_AVERAGE,
        'Average respiratory rate', UOM_BREATHS_PER_MINUTE, None
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_RESPIRATORY_RATE_MIN,
        MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MIN,
        'Minimum respiratory rate', UOM_BREATHS_PER_MINUTE, None
    ),
    WithingsSleepSummaryAttribute(
        MEAS_SLEEP_RESPIRATORY_RATE_MAX,
        MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MAX,
        'Maximum respiratory rate', UOM_BREATHS_PER_MINUTE, None
    ),
]

CONF_SENSORS = {}
WITHINGS_MEASUREMENTS_MAP = {}
for attr in WITHINGS_ATTRIBUTES:
    CONF_SENSORS[attr.measurement] = [
        attr.friendly_name,
        attr.unit_of_measurement
    ]
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
    vol.Optional(CONF_BASE_URL): cv.string,
    vol.Required(CONF_MEASUREMENTS, default=[]):
        vol.All(cv.ensure_list, [vol.In(CONF_SENSORS)]),

    # vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        # vol.All(cv.ensure_list, [vol.In(SENSORS)])
})


def get_credentials_from_file(hass: HomeAssistant, config_filename: str):
    """Attempt to load token data from file."""
    import nokia
    _LOGGER.debug('get_credentials_from_file')
    path = hass.config.path(config_filename)

    if not os.path.isfile(path):
        _LOGGER.debug('File does not exist: %s.', path)
        return None

    _LOGGER.debug('Loading json from: %s', path)
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


def write_credentials_to_file(
        hass: HomeAssistant,
        config_filename: str,
        creds
) -> None:
    """Attempt to store token data to file."""
    _LOGGER.debug('write_credentials_to_file')
    path = hass.config.path(config_filename)

    _LOGGER.debug('Ensuring path to file exists. %s', path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    _LOGGER.debug('Getting dict from creds object.')
    token_data = creds.__dict__

    _LOGGER.debug('Saving token data to file %s.', path)
    save_json(path, token_data)


def credentials_refreshed(hass: HomeAssistant,
                          config_filename: str,
                          creds) -> None:
    """Handle calls from  when the nokia api refreshes credentials."""
    _LOGGER.debug('async_credentials_refreshed')
    hass.add_job(write_credentials_to_file, hass, config_filename, creds)


class WithingsConfiguring:
    """Hold information used while configuring this component."""

    request_id = None

    def __init__(self,
                 hass,
                 config,
                 add_entities,
                 slug,
                 config_filename,
                 oauth_initialize_callback,
                 auth_client):
        """Constructor."""
        self.hass = hass
        self.config = config
        self.add_entities = add_entities
        self.slug = slug
        self.config_filename = config_filename
        self.oauth_initialize_callback = oauth_initialize_callback
        self.auth_client = auth_client


async def async_initialize(
        configuring: WithingsConfiguring,
        creds) -> WithingsDataManager:
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

    _LOGGER.debug(
        'Creating withings data manager for slug: %s',
        configuring.slug
    )
    data_manager = WithingsDataManager(
        configuring.slug,
        api
    )

    _LOGGER.debug('Attempting to refresh token.')
    await data_manager.async_refresh_token()

    _LOGGER.debug('Creating entities.')
    entities = []
    measurements = configuring.config.get(CONF_MEASUREMENTS)
    for measurement in measurements:
        _LOGGER.debug('Creating entity for %s', measurement)

        attribute = WITHINGS_MEASUREMENTS_MAP[measurement]

        entity = WithingsHealthSensor(data_manager, attribute)

        entities.append(entity)

    _LOGGER.debug('Adding entities.')
    configuring.add_entities(entities)

    return data_manager


async def async_oauth_initialize_callback(
        code: str,
        configuring: WithingsConfiguring) -> None:
    """Call after OAuth2 response is returned."""
    _LOGGER.debug('async_oauth_initialize_callback')

    _LOGGER.debug('Requesting credentials with code: %s.', code)
    creds = configuring.auth_client.get_credentials(code)

    _LOGGER.debug('Initializing data.')
    await async_initialize(configuring, creds)

    _LOGGER.debug('Finishing request.')
    configuring.hass.components.configurator.async_request_done(
        configuring.request_id
    )


async def async_setup_platform(hass: HomeAssistant,
                               config: HomeAssistantConfig,
                               add_entities,
                               discovery_info=None):
    """Validate the configuration and return an withings scanner."""
    import nokia

    profile = config.get(CONF_PROFILE)
    slug = slugify(profile)
    config_filename = WITHINGS_CONFIG_FILE.format(config[CONF_CLIENT_ID], slug)
    creds = await hass.async_add_job(
        get_credentials_from_file,
        hass,
        config_filename
    )
    callback_path = '%s/%s' % (
        WITHINGS_AUTH_CALLBACK_PATH,
        slug
    )
    callback_uri = '{}{}'.format(
        (config.get(CONF_BASE_URL) or hass.config.api.base_url).rstrip('/'),
        callback_path
    )

    _LOGGER.debug('Creating auth client with callback uri: %s', callback_uri)
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
        # No idea what sorts of exceptions will be coming from 3rd party
        # library. Catching everything.
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.info(
                'Failed to initialize. Reverting back to configure mode.',
                exc_info=True
            )

    _LOGGER.debug('Starting configuration for slug: %s', slug)
    hass.http.register_view(WithingsAuthCallbackView(slug, callback_path))

    configuring.request_id = hass.components.configurator.async_request_config(
        "Withings",
        # pylint: disable=line-too-long
        description="Authorization is required to get access to Withings data. After clicking the button below, be sure to choose the profile that maps to '%s'." % profile,  # noqa: E501
        link_name="Click here to authorize Home Assistant.",
        link_url=auth_client.get_authorize_url(),
    )

    if DATA_CONFIGURING not in hass.data:
        hass.data[DATA_CONFIGURING] = {}

    hass.data[DATA_CONFIGURING][slug] = configuring

    return True


class WithingsAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    def __init__(self, slug: str, url: str) -> None:
        """Constructor."""
        self.slug = slug
        self.url = url
        self.name = 'api:withings:callback:%s' % slug

    @callback
    def get(self, request):  # pylint: disable=no-self-use
        """Finish OAuth callback request."""
        _LOGGER.debug('Received request.')

        hass = request.app['hass']
        params = request.query
        response = web.HTTPFound('/states')
        _LOGGER.debug('Params: %s', params)

        if 'state' not in params or 'code' not in params:
            if 'error' in params:
                _LOGGER.error(
                    "Error authorizing Withings: %s", params['error'])
                return web.Response(
                    text='ERROR_0001: Withings provided an error: %s' %
                    params['error']
                )
            _LOGGER.error(
                "Error authorizing Withings. Invalid response returned")

            return web.Response(
                text='ERROR_0002: either state or code url parameters were not set.'  # noqa: E501
            )

        if DATA_CONFIGURING not in hass.data:
            _LOGGER.error("Withings configuration request not found")
            return web.Response(
                text='ERROR_0003: %s was not found in hass.data. This is a bug.' %  # noqa: E501
                DATA_CONFIGURING
            )

        if self.slug not in hass.data[DATA_CONFIGURING]:
            _LOGGER.error(
                "Withings configuration request for %s not found",
                self.slug
            )
            return web.Response(
                text='ERROR_0004: %s was not found in hass.data[%s].' % (
                    self.slug, DATA_CONFIGURING
                )
            )

        _LOGGER.debug('Calling async_oauth_initialize_callback')
        code = params['code']
        # state = params['state']
        configuring = hass.data[DATA_CONFIGURING][self.slug]
        oauth_initialize_callback = configuring.oauth_initialize_callback
        hass.async_create_task(oauth_initialize_callback(code, configuring))

        _LOGGER.debug('Returning response.')
        return response

    def __eq__(self, that):
        """Compare equality for two views."""
        return that is not None \
            and isinstance(that, WithingsAuthCallbackView) \
            and self.url == that.url \
            and self.name == that.name \
            and self.slug == that.slug


class WithingsHealthSensor(Entity):
    """Implementation of a Withings sensor."""

    def __init__(self,
                 data_manager: WithingsDataManager,
                 attribute: WithingsAttribute) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self._attribute = attribute
        self._state = None

        self._slug = self._data_manager.get_slug()
        self._user_id = self._data_manager.get_api().get_credentials().user_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'Withings %s %s' % (self._attribute.measurement, self._slug)

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'withings_%s_%s_%s' % (
            self._slug, self._user_id, slugify(self._attribute.measurement)
        )

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

    @property
    def attribute(self) -> WithingsAttribute:
        """Get withings attribute."""
        return self._attribute

    async def async_update(self) -> None:
        """Update the data."""
        _LOGGER.debug(
            'async_update slug: %s, measurement: %s, user_id: %s',
            self._slug, self._attribute.measurement, self._user_id
        )

        if isinstance(self._attribute, WithingsMeasureAttribute):
            _LOGGER.debug('Updating measures state.')
            await self._data_manager.async_update_measures()
            await self.async_update_measure(self._data_manager.get_measures())

        elif isinstance(self._attribute, WithingsSleepStateAttribute):
            _LOGGER.debug('Updating sleep state.')
            await self._data_manager.async_update_sleep()
            await self.async_update_sleep_state(self._data_manager.get_sleep())

        elif isinstance(self._attribute, WithingsSleepSummaryAttribute):
            _LOGGER.debug('Updating sleep summary state.')
            await self._data_manager.async_update_sleep_summary()
            await self.async_update_sleep_summary(
                self._data_manager.get_sleep_summary()
            )

    async def async_update_measure(self, data) -> None:
        """Update the measures data."""
        _LOGGER.debug('async_update_measure')

        if data is None:
            _LOGGER.error('Provided data is None. Not updating state.')
            return

        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement

        _LOGGER.debug(
            'Finding the unambiguous measure group with measure_type: %s.',
            measure_type
        )
        measure_groups = list(filter(
            lambda g: (
                not g.is_ambiguous() and
                g.get_measure(measure_type) is not None
            ),
            data
        ))

        if not measure_groups:
            _LOGGER.warning('No measure groups found.')
            return

        _LOGGER.debug(
            'Sorting list of %s measure groups by date created (DESC).',
            len(measure_groups)
        )
        measure_groups.sort(key=(lambda g: g.created), reverse=True)

        _LOGGER.debug(
            'Getting the first measure from the sorted measure groups.'
        )
        value = measure_groups[0].get_measure(measure_type)

        _LOGGER.debug(
            # pylint: disable=line-too-long
            'Determining state for measurement: %s, measure_type: %s, unit_of_measurement: %s, value: %s',  # noqa: E501
            measurement, measure_type, unit_of_measurement, value
        )

        if unit_of_measurement is UOM_MASS_KG:
            state = round(value, 1)

        elif unit_of_measurement is UOM_MASS_LB:
            state = round(value * 2.205, 2)

        elif unit_of_measurement is UOM_LENGTH_M:
            state = round(value, 2)

        elif unit_of_measurement is UOM_LENGTH_CM:
            state = round(value * 100, 1)

        elif unit_of_measurement is UOM_LENGTH_IN:
            state = round(value * 39.37, 2)

        elif unit_of_measurement is UOM_TEMP_C:
            state = round(value, 1)

        elif unit_of_measurement is UOM_TEMP_F:
            state = round((value * 1.8) + 32, 2)

        elif unit_of_measurement is UOM_PERCENT:
            state = round(value * 100, 1)

        elif unit_of_measurement is UOM_MMHG:
            state = round(value, 0)

        elif unit_of_measurement is UOM_BEATS_PER_MINUTE:
            state = round(value, 0)

        elif unit_of_measurement is UOM_IMPERIAL_HEIGHT:
            feet_raw = value * 3.281
            feet = int(feet_raw)
            inches_ratio = feet_raw - feet
            inches = round(inches_ratio * 12, 1)

            state = "%d' %d\"" % (feet, inches)

        elif unit_of_measurement is UOM_METERS_PER_SECOND:
            state = round(value, 0)

        else:
            state = round(value, 2)

        _LOGGER.debug('Setting state: %s', state)
        self._state = state

    async def async_update_sleep_state(self, data) -> None:
        """Update the sleep state data."""
        _LOGGER.debug('async_update_sleep_state')

        if data is None:
            _LOGGER.error(
                'Provided data is None, setting value to %s.',
                STATE_UNKNOWN
            )
            self._state = STATE_UNKNOWN
            return

        if not data.series:
            _LOGGER.warning(
                'No sleep data, setting value to %s.',
                STATE_UNKNOWN
            )
            self._state = STATE_UNKNOWN
            return

        series = sorted(data.series, key=lambda o: o.enddate, reverse=True)

        serie = series[0]

        state = None
        if serie.state == MEASURE_TYPE_SLEEP_STATE_AWAKE:
            state = STATE_AWAKE
        elif serie.state == MEASURE_TYPE_SLEEP_STATE_LIGHT:
            state = STATE_LIGHT
        elif serie.state == MEASURE_TYPE_SLEEP_STATE_DEEP:
            state = STATE_DEEP
        elif serie.state == MEASURE_TYPE_SLEEP_STATE_REM:
            state = STATE_REM
        else:
            state = STATE_UNKNOWN

        _LOGGER.debug('Setting state: %s', state)
        self._state = state

    async def async_update_sleep_summary(self, data) -> None:
        """Update the sleep summary data."""
        _LOGGER.debug('async_update_sleep_summary')

        if data is None:
            _LOGGER.error('Provided data is None. Not updating state.')
            return

        if not data.series:
            _LOGGER.warning('Sleep data has no series.')
            return

        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement

        _LOGGER.debug('Determining average value for: %s', measurement)
        count = 0
        total = 0
        for serie in data.series:
            if hasattr(serie, measure_type):
                count += 1
                total += getattr(serie, measure_type)

        value = total / count

        # Convert the units.
        state = None
        if unit_of_measurement is UOM_HOURS:
            state = round(value / 60, 1)

        else:
            state = value

        _LOGGER.debug('Setting state: %s', state)
        self._state = state
