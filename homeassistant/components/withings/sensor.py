"""Sensors flow for Withings."""
import typing as types

import nokia

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from . import const
from .common import (
    _LOGGER,
    NotAuthenticatedError,
    WithingsDataManager,
)

# There's only 3 calls (per profile) made to the withings api every 5
# minutes (see throttle values). This component wouldn't benefit
# much from parallel updates.
PARALLEL_UPDATES = 1


async def async_setup_entry(
        hass: HomeAssistantType,
        entry: ConfigEntry,
        async_add_entities: types.Callable[[types.List[Entity], bool], None]
):
    """Set up the sensor config entry."""
    profile = entry.data[const.PROFILE]
    credentials = nokia.NokiaCredentials()
    credentials.__dict__.update(entry.data[const.CREDENTIALS])

    def credentials_saver(credentials_param):
        _LOGGER.debug("Saving updated credentials.")
        entry.data[const.CREDENTIALS] = credentials_param
        hass.config_entries.async_update_entry(entry, data={**entry.data})

    _LOGGER.debug(
        "Creating nokia api instance with credentials %s",
        credentials
    )
    api = nokia.NokiaApi(
        credentials,
        refresh_cb=(lambda token: credentials_saver(
            api.credentials
        ))
    )

    _LOGGER.debug(
        "Creating withings data manager for profile: %s",
        profile
    )
    data_manager = WithingsDataManager(
        profile,
        api
    )

    _LOGGER.debug("Confirming we're authenticated")
    try:
        data_manager.check_authenticated()
    except NotAuthenticatedError:
        # Trigger new config flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                const.DOMAIN,
                context={
                    'source': const.SOURCE_USER,
                    const.PROFILE: profile
                },
                data={}
            )
        )
        return

    entities = create_sensor_entities(hass, data_manager)
    async_add_entities(entities, True)


def create_sensor_entities(
        hass: HomeAssistantType,
        data_manager: WithingsDataManager
):
    """Create sensor entities."""
    entities = []

    measures = hass.data.get(const.DOMAIN, {}) \
        .get(const.CONFIG, {}) \
        .get(const.MEASURES, list(WITHINGS_MEASUREMENTS_MAP))

    for attribute in WITHINGS_ATTRIBUTES:
        if attribute.measurement not in measures:
            _LOGGER.debug("Skipping measurement %s as it is not in the list of measurements to use", attribute.measurement)  # pylint: disable=line-too-long  # noqa: E501
            continue

        _LOGGER.debug(
            "Creating entity for measurement: %s, measure_type: %s, friendly_name: %s, unit_of_measurement: %s",  # pylint: disable=line-too-long  # noqa: E501
            attribute.measurement,
            attribute.measure_type,
            attribute.friendly_name,
            attribute.unit_of_measurement
        )

        entity = WithingsHealthSensor(data_manager, attribute)

        entities.append(entity)

    return entities


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
        super().__init__(
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
        const.MEAS_FAT_MASS_STONE, const.MEASURE_TYPE_FAT_MASS,
        'Fat Mass', const.UOM_MASS_STONE, 'mdi:weight'
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
        const.MEAS_FAT_FREE_MASS_STONE, const.MEASURE_TYPE_FAT_MASS_FREE,
        'Fat Free Mass', const.UOM_MASS_STONE, 'mdi:weight'
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
        const.MEAS_MUSCLE_MASS_STONE, const.MEASURE_TYPE_MUSCLE_MASS,
        'Muscle Mass', const.UOM_MASS_STONE, 'mdi:weight'
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
        const.MEAS_BONE_MASS_STONE, const.MEASURE_TYPE_BONE_MASS,
        'Bone Mass', const.UOM_MASS_STONE, 'mdi:weight'
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

    # These temperature values are automatically converted to
    # ha's configured system of measurement by the entity api.
    # There is no way to override this behaviour and there are
    # discussions to change this.
    # https://github.com/home-assistant/architecture/issues/10
    # So we set the OUM to celsius for now and let the Entity class
    # perform the necessary conversions.
    WithingsMeasureAttribute(
        const.MEAS_TEMP_AUTO, const.MEASURE_TYPE_TEMP,
        'Temperature', const.UOM_TEMP_C, 'mdi:thermometer'
    ),
    WithingsMeasureAttribute(
        const.MEAS_BODY_TEMP_AUTO, const.MEASURE_TYPE_BODY_TEMP,
        'Body Temperature', const.UOM_TEMP_C, 'mdi:thermometer'
    ),
    WithingsMeasureAttribute(
        const.MEAS_SKIN_TEMP_AUTO, const.MEASURE_TYPE_SKIN_TEMP,
        'Skin Temperature', const.UOM_TEMP_C, 'mdi:thermometer'
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

WITHINGS_MEASUREMENTS_MAP = {
    attr.measurement: attr for attr in WITHINGS_ATTRIBUTES
}


class WithingsHealthSensor(Entity):
    """Implementation of a Withings sensor."""

    def __init__(self,
                 data_manager: WithingsDataManager,
                 attribute: WithingsAttribute) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self._attribute = attribute
        self._state = None

        self._slug = self._data_manager.slug
        self._user_id = self._data_manager.api.get_credentials().user_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'Withings {} {}'.format(self._attribute.measurement, self._slug)

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'withings_{}_{}_{}'.format(
            self._slug,
            self._user_id,
            slugify(self._attribute.measurement)
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
    def device_state_attributes(self):
        """Get withings attributes."""
        return self._attribute.__dict__

    async def async_update(self) -> None:
        """Update the data."""
        _LOGGER.debug(
            "Async update slug: %s, measurement: %s, user_id: %s",
            self._slug, self._attribute.measurement, self._user_id
        )

        if isinstance(self._attribute, WithingsMeasureAttribute):
            _LOGGER.debug("Updating measures state")
            self._data_manager.update_measures()
            await self.async_update_measure(self._data_manager.measures)

        elif isinstance(self._attribute, WithingsSleepStateAttribute):
            _LOGGER.debug("Updating sleep state")
            self._data_manager.update_sleep()
            await self.async_update_sleep_state(self._data_manager.sleep)

        elif isinstance(self._attribute, WithingsSleepSummaryAttribute):
            _LOGGER.debug("Updating sleep summary state")
            self._data_manager.update_sleep_summary()
            await self.async_update_sleep_summary(
                self._data_manager.sleep_summary
            )

    async def async_update_measure(self, data) -> None:
        """Update the measures data."""
        if data is None:
            _LOGGER.error(
                "Provided data is None. Setting state to %s",
                None
            )
            self._state = None
            return

        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement

        _LOGGER.debug(
            "Finding the unambiguous measure group with measure_type: %s",
            measure_type
        )
        measure_groups = [g for g in data if (
            not g.is_ambiguous() and
            g.get_measure(measure_type) is not None
        )]

        if not measure_groups:
            _LOGGER.warning(
                "No measure groups found, setting state to %s",
                None
            )
            self._state = None
            return

        _LOGGER.debug(
            "Sorting list of %s measure groups by date created (DESC)",
            len(measure_groups)
        )
        measure_groups.sort(key=(lambda g: g.created), reverse=True)

        value = measure_groups[0].get_measure(measure_type)

        _LOGGER.debug(
            "Determining state for measurement: %s, measure_type: %s, unit_of_measurement: %s, value: %s",  # pylint: disable=line-too-long  # noqa: E501
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
            inches = int(round(inches_ratio * 12, 1))

            state = "{}' {}\"".format(feet, inches)

        elif unit_of_measurement is const.UOM_METERS_PER_SECOND:
            state = round(value, 0)

        else:
            state = round(value, 2)

        _LOGGER.debug("Setting state: %s", state)
        self._state = state

    async def async_update_sleep_state(self, data) -> None:
        """Update the sleep state data."""
        if data is None:
            _LOGGER.error(
                "Provided data is None. Setting state to %s",
                None
            )
            self._state = None
            return

        if not data.series:
            _LOGGER.warning(
                "No sleep data, setting state to %s",
                None
            )
            self._state = None
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
            state = None

        _LOGGER.debug("Setting state: %s", state)
        self._state = state

    async def async_update_sleep_summary(self, data) -> None:
        """Update the sleep summary data."""
        if data is None:
            _LOGGER.error(
                "Provided data is None. Setting state to %s",
                None
            )
            self._state = None
            return

        if not data.series:
            _LOGGER.warning(
                "Sleep data has no series, setting state to %s",
                None
            )
            self._state = None
            return

        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type
        unit_of_measurement = self._attribute.unit_of_measurement

        _LOGGER.debug("Determining average value for: %s", measurement)
        count = 0
        total = 0
        for serie in data.series:
            if hasattr(serie, measure_type):
                count += 1
                total += getattr(serie, measure_type)

        # Avoiding divide by zero error.
        if count == 0:
            self._state = 0
            return

        value = total / count

        # Convert the units.
        state = None
        if unit_of_measurement is const.UOM_HOURS:
            state = round(value / 60, 1)

        else:
            state = value

        _LOGGER.debug("Setting state: %s", state)
        self._state = state
