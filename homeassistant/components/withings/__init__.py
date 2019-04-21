"""
Support for the Withings API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/withings/
"""
import logging
import time
import datetime
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify, Throttle

from . import config_flow  # noqa  pylint_disable=unused-import
from . import const

DEPENDENCIES = ['api', 'http']
REQUIREMENTS = ['nokia==1.2.0']

_LOGGER = logging.getLogger(__name__)


class WithingsAttribute:
    """Base class for modeling withing data."""

    def __init__(self,
                 measurement: str,
                 measure_type,
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


WITHINGS_ATTRIBUTES = [
    WithingsMeasureAttribute(
        const.MEAS_WEIGHT_KG, const.MEASURE_TYPE_WEIGHT,
        'Weight', const.UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        const.MEAS_WEIGHT_LB, const.MEASURE_TYPE_WEIGHT,
        'Weight', const.UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        const.MEAS_WEIGHT_STONE, const.MEASURE_TYPE_WEIGHT,
        'Weight', const.UOM_MASS_STONE, 'mdi:weight'
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_MASS_KG, const.MEASURE_TYPE_FAT_MASS,
        'Fat Mass', const.UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_MASS_LB, const.MEASURE_TYPE_FAT_MASS,
        'Fat Mass', const.UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_FREE_MASS_KG, const.MEASURE_TYPE_FAT_MASS_FREE,
        'Fat Free Mass', const.UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_FREE_MASS_LB, const.MEASURE_TYPE_FAT_MASS_FREE,
        'Fat Free Mass', const.UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        const.MEAS_MUSCLE_MASS_KG, const.MEASURE_TYPE_MUSCLE_MASS,
        'Muscle Mass', const.UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        const.MEAS_MUSCLE_MASS_LB, const.MEASURE_TYPE_MUSCLE_MASS,
        'Muscle Mass', const.UOM_MASS_LB, 'mdi:weight-pound'
    ),
    WithingsMeasureAttribute(
        const.MEAS_BONE_MASS_KG, const.MEASURE_TYPE_BONE_MASS,
        'Bone Mass', const.UOM_MASS_KG, 'mdi:weight-kilogram'
    ),
    WithingsMeasureAttribute(
        const.MEAS_BONE_MASS_LB, const.MEASURE_TYPE_BONE_MASS,
        'Bone Mass', const.UOM_MASS_LB, 'mdi:weight-pound'
    ),

    WithingsMeasureAttribute(
        const.MEAS_HEIGHT_M, const.MEASURE_TYPE_HEIGHT,
        'Height', const.UOM_LENGTH_M, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEIGHT_CM, const.MEASURE_TYPE_HEIGHT,
        'Height', const.UOM_LENGTH_CM, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEIGHT_IN, const.MEASURE_TYPE_HEIGHT,
        'Height', const.UOM_LENGTH_IN, 'mdi:ruler'
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEIGHT_IMP, const.MEASURE_TYPE_HEIGHT,
        'Height', const.UOM_IMPERIAL_HEIGHT, 'mdi:ruler'
    ),

    WithingsMeasureAttribute(
        const.MEAS_TEMP_C, const.MEASURE_TYPE_TEMP,
        'Temperature', const.UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        const.MEAS_TEMP_F, const.MEASURE_TYPE_TEMP,
        'Temperature', const.UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),
    WithingsMeasureAttribute(
        const.MEAS_BODY_TEMP_C, const.MEASURE_TYPE_BODY_TEMP,
        'Body Temperature', const.UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        const.MEAS_BODY_TEMP_F, const.MEASURE_TYPE_BODY_TEMP,
        'Body Temperature', const.UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),
    WithingsMeasureAttribute(
        const.MEAS_SKIN_TEMP_C, const.MEASURE_TYPE_SKIN_TEMP,
        'Skin Temperature', const.UOM_TEMP_C, 'mdi:temperature-celsius'
    ),
    WithingsMeasureAttribute(
        const.MEAS_SKIN_TEMP_F, const.MEASURE_TYPE_SKIN_TEMP,
        'Skin Temperature', const.UOM_TEMP_F, 'mdi:temperature-fahrenheit'
    ),

    WithingsMeasureAttribute(
        const.MEAS_FAT_RATIO_PCT, const.MEASURE_TYPE_FAT_RATIO,
        'Fat Ratio', const.UOM_PERCENT, None
    ),
    WithingsMeasureAttribute(
        const.MEAS_DIASTOLIC_MMHG, const.MEASURE_TYPE_DIASTOLIC_BP,
        'Diastolic Blood Pressure', const.UOM_MMHG, None
    ),
    WithingsMeasureAttribute(
        const.MEAS_SYSTOLIC_MMGH, const.MEASURE_TYPE_SYSTOLIC_BP,
        'Systolic Blood Pressure', const.UOM_MMHG, None
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEART_PULSE_BPM, const.MEASURE_TYPE_HEART_PULSE,
        'Heart Pulse', const.UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsMeasureAttribute(
        const.MEAS_SPO2_PCT, const.MEASURE_TYPE_SPO2,
        'SP02', const.UOM_PERCENT, None
    ),
    WithingsMeasureAttribute(
        const.MEAS_HYDRATION, const.MEASURE_TYPE_HYDRATION,
        'Hydration', '', 'mdi:water'
    ),
    WithingsMeasureAttribute(
        const.MEAS_PWV, const.MEASURE_TYPE_PWV,
        'Pulse Wave Velocity', const.UOM_METERS_PER_SECOND, None
    ),

    WithingsSleepStateAttribute(
        const.MEAS_SLEEP_STATE,
        'Sleep state',
        None,
        'mdi:sleep'
    ),

    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_WAKEUP_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_WAKEUP_DURATION,
        'Wakeup time', const.UOM_HOURS, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_LIGHT_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_LIGHT_DURATION,
        'Light sleep', const.UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_DEEP_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_DEEP_DURATION,
        'Deep sleep', const.UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_REM_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_REM_DURATION,
        'REM sleep', const.UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_WAKEUP_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_WAKEUP_DURATION,
        'Wakeup time', const.UOM_MINUTES, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_LIGHT_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_LIGHT_DURATION,
        'Light sleep', const.UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_DEEP_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_DEEP_DURATION,
        'Deep sleep', const.UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_REM_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_REM_DURATION,
        'REM sleep', const.UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_WAKEUP_COUNT, const.MEASURE_TYPE_SLEEP_WAKUP_COUNT,
        'Wakeup count', const.UOM_FREQUENCY, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOSLEEP_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_TOSLEEP_DURATION,
        'Time to sleep', const.UOM_HOURS, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOWAKEUP_DURATION_HOURS,
        const.MEASURE_TYPE_SLEEP_TOWAKEUP_DURATION,
        'Time to wakeup', const.UOM_HOURS, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOSLEEP_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_TOSLEEP_DURATION,
        'Time to sleep', const.UOM_MINUTES, 'mdi:sleep'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES,
        const.MEASURE_TYPE_SLEEP_TOWAKEUP_DURATION,
        'Time to wakeup', const.UOM_MINUTES, 'mdi:sleep-off'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_AVERAGE,
        const.MEASURE_TYPE_SLEEP_HEART_RATE_AVERAGE,
        'Average heart rate', const.UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_MIN,
        const.MEASURE_TYPE_SLEEP_HEART_RATE_MIN,
        'Minimum heart rate', const.UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_MAX,
        const.MEASURE_TYPE_SLEEP_HEART_RATE_MAX,
        'Maximum heart rate', const.UOM_BEATS_PER_MINUTE, 'mdi:heart-pulse'
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE,
        const.MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_AVERAGE,
        'Average respiratory rate', const.UOM_BREATHS_PER_MINUTE, None
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_MIN,
        const.MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MIN,
        'Minimum respiratory rate', const.UOM_BREATHS_PER_MINUTE, None
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_MAX,
        const.MEASURE_TYPE_SLEEP_RESPIRATORY_RATE_MAX,
        'Maximum respiratory rate', const.UOM_BREATHS_PER_MINUTE, None
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


CONFIG_SCHEMA = vol.Schema(
    {
        const.DOMAIN:
            vol.Schema({
                vol.Required(const.CLIENT_ID): cv.string,
                vol.Required(const.CLIENT_SECRET): cv.string,
                vol.Optional(const.BASE_URL): cv.string,
                vol.Required(const.PROFILES): [cv.string],
            })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Withings component."""
    if const.DOMAIN not in config:
        return True

    conf = config[const.DOMAIN]

    base_url = hass.config.api.base_url.rstrip('/')
    if const.BASE_URL in conf and conf[const.BASE_URL] is not None:
        base_url = conf[const.BASE_URL].rstrip('/')

    for profile in conf[const.PROFILES]:
        config_flow.register_flow_implementation(
            hass,
            conf[const.CLIENT_ID],
            conf[const.CLIENT_SECRET],
            base_url,
            profile
        )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={'source': const.SOURCE_PROFILE},
            data={}
        )
    )

    return True


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

    @Throttle(const.SCAN_INTERVAL)
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

    @Throttle(const.SCAN_INTERVAL)
    async def async_update_measures(self):
        """Update the measures data."""
        _LOGGER.debug('async_update_measures')

        self._measures = self._api.get_measures()

        return self._measures

    @Throttle(const.SCAN_INTERVAL)
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

    @Throttle(const.SCAN_INTERVAL)
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

        if unit_of_measurement is const.UOM_MASS_KG:
            state = round(value, 1)

        elif unit_of_measurement is const.UOM_MASS_LB:
            state = round(value * 2.205, 2)

        elif unit_of_measurement is const.UOM_MASS_STONE:
            state = round(value * 0.157473, 2)

        elif unit_of_measurement is const.UOM_LENGTH_M:
            state = round(value, 2)

        elif unit_of_measurement is const.UOM_LENGTH_CM:
            state = round(value * 100, 1)

        elif unit_of_measurement is const.UOM_LENGTH_IN:
            state = round(value * 39.37, 2)

        elif unit_of_measurement is const.UOM_TEMP_C:
            state = round(value, 1)

        elif unit_of_measurement is const.UOM_TEMP_F:
            state = round((value * 1.8) + 32, 2)

        elif unit_of_measurement is const.UOM_PERCENT:
            state = round(value * 100, 1)

        elif unit_of_measurement is const.UOM_MMHG:
            state = round(value, 0)

        elif unit_of_measurement is const.UOM_BEATS_PER_MINUTE:
            state = round(value, 0)

        elif unit_of_measurement is const.UOM_IMPERIAL_HEIGHT:
            feet_raw = value * 3.281
            feet = int(feet_raw)
            inches_ratio = feet_raw - feet
            inches = round(inches_ratio * 12, 1)

            state = "%d' %d\"" % (feet, inches)

        elif unit_of_measurement is const.UOM_METERS_PER_SECOND:
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
                const.STATE_UNKNOWN
            )
            self._state = const.STATE_UNKNOWN
            return

        if not data.series:
            _LOGGER.warning(
                'No sleep data, setting value to %s.',
                const.STATE_UNKNOWN
            )
            self._state = const.STATE_UNKNOWN
            return

        series = sorted(data.series, key=lambda o: o.enddate, reverse=True)

        serie = series[0]

        state = None
        if serie.state == const.MEASURE_TYPE_SLEEP_STATE_AWAKE:
            state = const.STATE_AWAKE
        elif serie.state == const.MEASURE_TYPE_SLEEP_STATE_LIGHT:
            state = const.STATE_LIGHT
        elif serie.state == const.MEASURE_TYPE_SLEEP_STATE_DEEP:
            state = const.STATE_DEEP
        elif serie.state == const.MEASURE_TYPE_SLEEP_STATE_REM:
            state = const.STATE_REM
        else:
            state = const.STATE_UNKNOWN

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
        if unit_of_measurement is const.UOM_HOURS:
            state = round(value / 60, 1)

        else:
            state = value

        _LOGGER.debug('Setting state: %s', state)
        self._state = state
