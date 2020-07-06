"""Tests for the Withings component."""
from typing import Any
from unittest.mock import patch

import arrow
import pytz
from withings_api.common import (
    GetSleepSummaryData,
    GetSleepSummarySerie,
    MeasureGetMeasGroup,
    MeasureGetMeasGroupAttrib,
    MeasureGetMeasGroupCategory,
    MeasureGetMeasMeasure,
    MeasureGetMeasResponse,
    MeasureType,
    NotifyAppli,
    SleepGetSummaryResponse,
    SleepModel,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.withings.common import (
    WITHINGS_MEASUREMENTS_MAP,
    WithingsAttribute,
    async_get_entity_id,
    get_platform_attributes,
)
from homeassistant.components.withings.const import Measurement
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import ComponentFactory, new_profile_config

PERSON0 = new_profile_config(
    "person0",
    0,
    api_response_measure_get_meas=MeasureGetMeasResponse(
        measuregrps=(
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow().shift(hours=-1),
                date=arrow.utcnow().shift(hours=-1),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=70),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=5
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=60
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=50
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=10),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=2),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=20
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=70
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=70
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=100
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=60
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=95),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=95
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=100
                    ),
                ),
            ),
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow().shift(hours=-2),
                date=arrow.utcnow().shift(hours=-2),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=71),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=11),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=21),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=21
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=101
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=96),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=96
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=101
                    ),
                ),
            ),
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER_AMBIGUOUS,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow(),
                date=arrow.utcnow(),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=71),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=4
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=11),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=201),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=34
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=21
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=101
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=98),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=96
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=102
                    ),
                ),
            ),
        ),
        more=False,
        timezone=pytz.UTC,
        updatetime=arrow.get("2019-08-01"),
        offset=0,
    ),
    api_response_sleep_get_summary=SleepGetSummaryResponse(
        more=False,
        offset=0,
        series=(
            GetSleepSummarySerie(
                timezone=pytz.UTC,
                model=SleepModel.SLEEP_MONITOR,
                startdate=arrow.get("2019-02-01"),
                enddate=arrow.get("2019-02-01"),
                date=arrow.get("2019-02-01"),
                modified=arrow.get(12345),
                data=GetSleepSummaryData(
                    breathing_disturbances_intensity=110,
                    deepsleepduration=111,
                    durationtosleep=112,
                    durationtowakeup=113,
                    hr_average=114,
                    hr_max=115,
                    hr_min=116,
                    lightsleepduration=117,
                    remsleepduration=118,
                    rr_average=119,
                    rr_max=120,
                    rr_min=121,
                    sleep_score=122,
                    snoring=123,
                    snoringepisodecount=124,
                    wakeupcount=125,
                    wakeupduration=126,
                ),
            ),
            GetSleepSummarySerie(
                timezone=pytz.UTC,
                model=SleepModel.SLEEP_MONITOR,
                startdate=arrow.get("2019-02-01"),
                enddate=arrow.get("2019-02-01"),
                date=arrow.get("2019-02-01"),
                modified=arrow.get(12345),
                data=GetSleepSummaryData(
                    breathing_disturbances_intensity=210,
                    deepsleepduration=211,
                    durationtosleep=212,
                    durationtowakeup=213,
                    hr_average=214,
                    hr_max=215,
                    hr_min=216,
                    lightsleepduration=217,
                    remsleepduration=218,
                    rr_average=219,
                    rr_max=220,
                    rr_min=221,
                    sleep_score=222,
                    snoring=223,
                    snoringepisodecount=224,
                    wakeupcount=225,
                    wakeupduration=226,
                ),
            ),
        ),
    ),
)

EXPECTED_DATA = (
    (PERSON0, Measurement.WEIGHT_KG, 70.0),
    (PERSON0, Measurement.FAT_MASS_KG, 5.0),
    (PERSON0, Measurement.FAT_FREE_MASS_KG, 60.0),
    (PERSON0, Measurement.MUSCLE_MASS_KG, 50.0),
    (PERSON0, Measurement.BONE_MASS_KG, 10.0),
    (PERSON0, Measurement.HEIGHT_M, 2.0),
    (PERSON0, Measurement.FAT_RATIO_PCT, 0.07),
    (PERSON0, Measurement.DIASTOLIC_MMHG, 70.0),
    (PERSON0, Measurement.SYSTOLIC_MMGH, 100.0),
    (PERSON0, Measurement.HEART_PULSE_BPM, 60.0),
    (PERSON0, Measurement.SPO2_PCT, 0.95),
    (PERSON0, Measurement.HYDRATION, 0.95),
    (PERSON0, Measurement.PWV, 100.0),
    (PERSON0, Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY, 160.0),
    (PERSON0, Measurement.SLEEP_DEEP_DURATION_SECONDS, 322),
    (PERSON0, Measurement.SLEEP_HEART_RATE_AVERAGE, 164.0),
    (PERSON0, Measurement.SLEEP_HEART_RATE_MAX, 165.0),
    (PERSON0, Measurement.SLEEP_HEART_RATE_MIN, 166.0),
    (PERSON0, Measurement.SLEEP_LIGHT_DURATION_SECONDS, 334),
    (PERSON0, Measurement.SLEEP_REM_DURATION_SECONDS, 336),
    (PERSON0, Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE, 169.0),
    (PERSON0, Measurement.SLEEP_RESPIRATORY_RATE_MAX, 170.0),
    (PERSON0, Measurement.SLEEP_RESPIRATORY_RATE_MIN, 171.0),
    (PERSON0, Measurement.SLEEP_SCORE, 222),
    (PERSON0, Measurement.SLEEP_SNORING, 173.0),
    (PERSON0, Measurement.SLEEP_SNORING_EPISODE_COUNT, 348),
    (PERSON0, Measurement.SLEEP_TOSLEEP_DURATION_SECONDS, 162.0),
    (PERSON0, Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS, 163.0),
    (PERSON0, Measurement.SLEEP_WAKEUP_COUNT, 350),
    (PERSON0, Measurement.SLEEP_WAKEUP_DURATION_SECONDS, 176.0),
)


def async_assert_state_equals(
    entity_id: str, state_obj: State, expected: Any, attribute: WithingsAttribute
) -> None:
    """Assert at given state matches what is expected."""
    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {attribute.measurement}, {entity_id}"
    )


async def test_sensor_default_enabled_entities(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test entities enabled by default."""
    entity_registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()

    await component_factory.configure_component(profile_configs=(PERSON0,))

    # Assert entities should not exist yet.
    for attribute in get_platform_attributes(SENSOR_DOMAIN):
        assert not await async_get_entity_id(hass, attribute, PERSON0.user_id)

    # person 0
    await component_factory.setup_profile(PERSON0.user_id)

    # Assert entities should exist.
    for attribute in get_platform_attributes(SENSOR_DOMAIN):
        entity_id = await async_get_entity_id(hass, attribute, PERSON0.user_id)
        assert entity_id
        assert entity_registry.async_is_registered(entity_id)

    resp = await component_factory.call_webhook(PERSON0.user_id, NotifyAppli.SLEEP)
    assert resp.message_code == 0

    resp = await component_factory.call_webhook(PERSON0.user_id, NotifyAppli.WEIGHT)
    assert resp.message_code == 0

    for person, measurement, expected in EXPECTED_DATA:
        attribute = WITHINGS_MEASUREMENTS_MAP[measurement]
        entity_id = await async_get_entity_id(hass, attribute, person.user_id)
        state_obj = hass.states.get(entity_id)

        if attribute.enabled_by_default:
            async_assert_state_equals(entity_id, state_obj, expected, attribute)
        else:
            assert state_obj is None

    # Unload
    await component_factory.unload(PERSON0)


async def test_all_entities(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test all entities."""
    entity_registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()

    with patch(
        "homeassistant.components.withings.sensor.BaseWithingsSensor.entity_registry_enabled_default"
    ) as enabled_by_default_mock:
        enabled_by_default_mock.return_value = True

        await component_factory.configure_component(profile_configs=(PERSON0,))

        # Assert entities should not exist yet.
        for attribute in get_platform_attributes(SENSOR_DOMAIN):
            assert not await async_get_entity_id(hass, attribute, PERSON0.user_id)

        # person 0
        await component_factory.setup_profile(PERSON0.user_id)

        # Assert entities should exist.
        for attribute in get_platform_attributes(SENSOR_DOMAIN):
            entity_id = await async_get_entity_id(hass, attribute, PERSON0.user_id)
            assert entity_id
            assert entity_registry.async_is_registered(entity_id)

        resp = await component_factory.call_webhook(PERSON0.user_id, NotifyAppli.SLEEP)
        assert resp.message_code == 0

        resp = await component_factory.call_webhook(PERSON0.user_id, NotifyAppli.WEIGHT)
        assert resp.message_code == 0

        for person, measurement, expected in EXPECTED_DATA:
            attribute = WITHINGS_MEASUREMENTS_MAP[measurement]
            entity_id = await async_get_entity_id(hass, attribute, person.user_id)
            state_obj = hass.states.get(entity_id)

            async_assert_state_equals(entity_id, state_obj, expected, attribute)

    # Unload
    await component_factory.unload(PERSON0)
