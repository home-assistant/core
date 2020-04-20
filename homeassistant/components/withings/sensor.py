"""Sensors flow for Withings."""
from typing import Callable, List, Union

from withings_api.common import (
    GetSleepSummaryField,
    MeasureGetMeasResponse,
    MeasureGroupAttribs,
    MeasureType,
    SleepGetSummaryResponse,
    get_measure_value,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    MASS_KILOGRAMS,
    SPEED_METERS_PER_SECOND,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import const
from .common import _LOGGER, WithingsDataManager, get_data_manager

# There's only 3 calls (per profile) made to the withings api every 5
# minutes (see throttle values). This component wouldn't benefit
# much from parallel updates.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    data_manager = get_data_manager(hass, entry, implementation)
    user_id = entry.data["token"]["userid"]

    entities = create_sensor_entities(data_manager, user_id)
    async_add_entities(entities, True)


class WithingsAttribute:
    """Base class for modeling withing data."""

    def __init__(
        self,
        measurement: str,
        measure_type,
        friendly_name: str,
        unit_of_measurement: str,
        icon: str,
    ) -> None:
        """Initialize attribute."""
        self.measurement = measurement
        self.measure_type = measure_type
        self.friendly_name = friendly_name
        self.unit_of_measurement = unit_of_measurement
        self.icon = icon


class WithingsMeasureAttribute(WithingsAttribute):
    """Model measure attributes."""


class WithingsSleepSummaryAttribute(WithingsAttribute):
    """Models sleep summary attributes."""


WITHINGS_ATTRIBUTES = [
    WithingsMeasureAttribute(
        const.MEAS_WEIGHT_KG,
        MeasureType.WEIGHT,
        "Weight",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_MASS_KG,
        MeasureType.FAT_MASS_WEIGHT,
        "Fat Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_FREE_MASS_KG,
        MeasureType.FAT_FREE_MASS,
        "Fat Free Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
    ),
    WithingsMeasureAttribute(
        const.MEAS_MUSCLE_MASS_KG,
        MeasureType.MUSCLE_MASS,
        "Muscle Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
    ),
    WithingsMeasureAttribute(
        const.MEAS_BONE_MASS_KG,
        MeasureType.BONE_MASS,
        "Bone Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEIGHT_M,
        MeasureType.HEIGHT,
        "Height",
        const.UOM_LENGTH_M,
        "mdi:ruler",
    ),
    WithingsMeasureAttribute(
        const.MEAS_TEMP_C,
        MeasureType.TEMPERATURE,
        "Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
    ),
    WithingsMeasureAttribute(
        const.MEAS_BODY_TEMP_C,
        MeasureType.BODY_TEMPERATURE,
        "Body Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
    ),
    WithingsMeasureAttribute(
        const.MEAS_SKIN_TEMP_C,
        MeasureType.SKIN_TEMPERATURE,
        "Skin Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
    ),
    WithingsMeasureAttribute(
        const.MEAS_FAT_RATIO_PCT,
        MeasureType.FAT_RATIO,
        "Fat Ratio",
        UNIT_PERCENTAGE,
        None,
    ),
    WithingsMeasureAttribute(
        const.MEAS_DIASTOLIC_MMHG,
        MeasureType.DIASTOLIC_BLOOD_PRESSURE,
        "Diastolic Blood Pressure",
        const.UOM_MMHG,
        None,
    ),
    WithingsMeasureAttribute(
        const.MEAS_SYSTOLIC_MMGH,
        MeasureType.SYSTOLIC_BLOOD_PRESSURE,
        "Systolic Blood Pressure",
        const.UOM_MMHG,
        None,
    ),
    WithingsMeasureAttribute(
        const.MEAS_HEART_PULSE_BPM,
        MeasureType.HEART_RATE,
        "Heart Pulse",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
    ),
    WithingsMeasureAttribute(
        const.MEAS_SPO2_PCT, MeasureType.SP02, "SP02", UNIT_PERCENTAGE, None
    ),
    WithingsMeasureAttribute(
        const.MEAS_HYDRATION,
        MeasureType.HYDRATION,
        "Hydration",
        UNIT_PERCENTAGE,
        "mdi:water",
    ),
    WithingsMeasureAttribute(
        const.MEAS_PWV,
        MeasureType.PULSE_WAVE_VELOCITY,
        "Pulse Wave Velocity",
        SPEED_METERS_PER_SECOND,
        None,
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_WAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.WAKEUP_DURATION.value,
        "Wakeup time",
        TIME_SECONDS,
        "mdi:sleep-off",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_LIGHT_DURATION_SECONDS,
        GetSleepSummaryField.LIGHT_SLEEP_DURATION.value,
        "Light sleep",
        TIME_SECONDS,
        "mdi:sleep",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_DEEP_DURATION_SECONDS,
        GetSleepSummaryField.DEEP_SLEEP_DURATION.value,
        "Deep sleep",
        TIME_SECONDS,
        "mdi:sleep",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_REM_DURATION_SECONDS,
        GetSleepSummaryField.REM_SLEEP_DURATION.value,
        "REM sleep",
        TIME_SECONDS,
        "mdi:sleep",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_WAKEUP_COUNT,
        GetSleepSummaryField.WAKEUP_COUNT.value,
        "Wakeup count",
        const.UOM_FREQUENCY,
        "mdi:sleep-off",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOSLEEP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_SLEEP.value,
        "Time to sleep",
        TIME_SECONDS,
        "mdi:sleep",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_TOWAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_WAKEUP.value,
        "Time to wakeup",
        TIME_SECONDS,
        "mdi:sleep-off",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_AVERAGE,
        GetSleepSummaryField.HR_AVERAGE.value,
        "Average heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_MIN,
        GetSleepSummaryField.HR_MIN.value,
        "Minimum heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_HEART_RATE_MAX,
        GetSleepSummaryField.HR_MAX.value,
        "Maximum heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE,
        GetSleepSummaryField.RR_AVERAGE.value,
        "Average respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_MIN,
        GetSleepSummaryField.RR_MIN.value,
        "Minimum respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
    ),
    WithingsSleepSummaryAttribute(
        const.MEAS_SLEEP_RESPIRATORY_RATE_MAX,
        GetSleepSummaryField.RR_MAX.value,
        "Maximum respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
    ),
]

WITHINGS_MEASUREMENTS_MAP = {attr.measurement: attr for attr in WITHINGS_ATTRIBUTES}


class WithingsHealthSensor(Entity):
    """Implementation of a Withings sensor."""

    def __init__(
        self,
        data_manager: WithingsDataManager,
        attribute: WithingsAttribute,
        user_id: str,
    ) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self._attribute = attribute
        self._state = None

        self._slug = self._data_manager.slug
        self._user_id = user_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Withings {self._attribute.measurement} {self._slug}"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return (
            f"withings_{self._slug}_{self._user_id}_"
            f"{slugify(self._attribute.measurement)}"
        )

    @property
    def state(self) -> Union[str, int, float, None]:
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
    def device_state_attributes(self) -> None:
        """Get withings attributes."""
        return self._attribute.__dict__

    async def async_update(self) -> None:
        """Update the data."""
        _LOGGER.debug(
            "Async update slug: %s, measurement: %s, user_id: %s",
            self._slug,
            self._attribute.measurement,
            self._user_id,
        )

        if isinstance(self._attribute, WithingsMeasureAttribute):
            _LOGGER.debug("Updating measures state")
            await self._data_manager.update_measures()
            await self.async_update_measure(self._data_manager.measures)

        elif isinstance(self._attribute, WithingsSleepSummaryAttribute):
            _LOGGER.debug("Updating sleep summary state")
            await self._data_manager.update_sleep_summary()
            await self.async_update_sleep_summary(self._data_manager.sleep_summary)

    async def async_update_measure(self, data: MeasureGetMeasResponse) -> None:
        """Update the measures data."""
        measure_type = self._attribute.measure_type

        _LOGGER.debug(
            "Finding the unambiguous measure group with measure_type: %s", measure_type
        )

        value = get_measure_value(data, measure_type, MeasureGroupAttribs.UNAMBIGUOUS)

        if value is None:
            _LOGGER.debug("Could not find a value, setting state to %s", None)
            self._state = None
            return

        self._state = round(value, 2)

    async def async_update_sleep_summary(self, data: SleepGetSummaryResponse) -> None:
        """Update the sleep summary data."""
        if not data.series:
            _LOGGER.debug("Sleep data has no series, setting state to %s", None)
            self._state = None
            return

        measurement = self._attribute.measurement
        measure_type = self._attribute.measure_type

        _LOGGER.debug("Determining total value for: %s", measurement)
        total = 0
        for serie in data.series:
            data = serie.data
            value = 0
            if measure_type == GetSleepSummaryField.REM_SLEEP_DURATION.value:
                value = data.remsleepduration
            elif measure_type == GetSleepSummaryField.WAKEUP_DURATION.value:
                value = data.wakeupduration
            elif measure_type == GetSleepSummaryField.LIGHT_SLEEP_DURATION.value:
                value = data.lightsleepduration
            elif measure_type == GetSleepSummaryField.DEEP_SLEEP_DURATION.value:
                value = data.deepsleepduration
            elif measure_type == GetSleepSummaryField.WAKEUP_COUNT.value:
                value = data.wakeupcount
            elif measure_type == GetSleepSummaryField.DURATION_TO_SLEEP.value:
                value = data.durationtosleep
            elif measure_type == GetSleepSummaryField.DURATION_TO_WAKEUP.value:
                value = data.durationtowakeup
            elif measure_type == GetSleepSummaryField.HR_AVERAGE.value:
                value = data.hr_average
            elif measure_type == GetSleepSummaryField.HR_MIN.value:
                value = data.hr_min
            elif measure_type == GetSleepSummaryField.HR_MAX.value:
                value = data.hr_max
            elif measure_type == GetSleepSummaryField.RR_AVERAGE.value:
                value = data.rr_average
            elif measure_type == GetSleepSummaryField.RR_MIN.value:
                value = data.rr_min
            elif measure_type == GetSleepSummaryField.RR_MAX.value:
                value = data.rr_max

            # Sometimes a None is provided for value, default to 0.
            total += value or 0

        self._state = round(total, 4)


def create_sensor_entities(
    data_manager: WithingsDataManager, user_id: str
) -> List[WithingsHealthSensor]:
    """Create sensor entities."""
    entities = []

    for attribute in WITHINGS_ATTRIBUTES:
        _LOGGER.debug(
            "Creating entity for measurement: %s, measure_type: %s,"
            "friendly_name: %s, unit_of_measurement: %s",
            attribute.measurement,
            attribute.measure_type,
            attribute.friendly_name,
            attribute.unit_of_measurement,
        )

        entity = WithingsHealthSensor(data_manager, attribute, user_id)

        entities.append(entity)

    return entities
