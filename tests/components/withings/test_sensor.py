"""Tests for the Withings component."""
from unittest.mock import MagicMock, patch

import asynctest
from nokia import NokiaApi, NokiaMeasures, NokiaSleep, NokiaSleepSummary
import pytest

from homeassistant.components.withings import (
    DOMAIN
)
from homeassistant.components.withings.common import (
    NotAuthenticatedError
)
import homeassistant.components.withings.const as const
from homeassistant.components.withings.sensor import async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .common import nokia_sleep_response
from .conftest import WithingsFactory, WithingsFactoryConfig


def get_entity_id(measure, profile):
    """Get an entity id for a measure and profile."""
    return 'sensor.{}_{}_{}'.format(
        DOMAIN,
        measure,
        slugify(profile)
    )


def assert_state_equals(
        hass: HomeAssistantType,
        profile: str,
        measure: str,
        expected
):
    """Assert the state of a withings sensor."""
    entity_id = get_entity_id(measure, profile)
    state_obj = hass.states.get(entity_id)

    assert state_obj, \
        "Expected entity {} to exist but it did not".format(
            entity_id
        )

    assert state_obj.state == str(expected), \
        "Expected {} but was {} for measure {}".format(
            expected,
            state_obj.state,
            measure
        )


async def test_health_sensor_properties(
        withings_factory: WithingsFactory
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(
        measures=[
            const.MEAS_HEIGHT_CM
        ]
    ))

    await data.configure_all(
        WithingsFactoryConfig.PROFILE_1,
        'authorization_code'
    )

    state = data.hass.states.get('sensor.withings_height_cm_person_1')
    state_dict = state.as_dict()
    assert state_dict.get('state') == '200'
    assert state_dict.get('attributes') == {
        'measurement': 'height_cm',
        'measure_type': 4,
        'friendly_name': "Withings height_cm person_1",
        'unit_of_measurement': 'cm',
        'icon': 'mdi:ruler',
    }


async def test_health_sensor_temperature_fahrenheit(
        withings_factory: WithingsFactory
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(
        unit_system='imperial',
        measures=[
            const.MEAS_TEMP_AUTO,
            const.MEAS_BODY_TEMP_AUTO,
            const.MEAS_SKIN_TEMP_AUTO
        ],
        throttle_interval=0
    ))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, 'authorization_code')

    assert_state_equals(
        data.hass,
        profile,
        const.MEAS_TEMP_AUTO,
        104
    )
    assert_state_equals(
        data.hass,
        profile,
        const.MEAS_BODY_TEMP_AUTO,
        95
    )
    assert_state_equals(
        data.hass,
        profile,
        const.MEAS_SKIN_TEMP_AUTO,
        68
    )

SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, 70),
    (const.MEAS_WEIGHT_LB, 154.35),
    (const.MEAS_WEIGHT_STONE, 11.02),
    (const.MEAS_FAT_MASS_KG, 5),
    (const.MEAS_FAT_MASS_LB, 11.03),
    (const.MEAS_FAT_MASS_STONE, 0.79),
    (const.MEAS_FAT_FREE_MASS_KG, 60),
    (const.MEAS_FAT_FREE_MASS_LB, 132.3),
    (const.MEAS_FAT_FREE_MASS_STONE, 9.45),
    (const.MEAS_MUSCLE_MASS_KG, 50),
    (const.MEAS_MUSCLE_MASS_LB, 110.25),
    (const.MEAS_MUSCLE_MASS_STONE, 7.87),
    (const.MEAS_BONE_MASS_KG, 10),
    (const.MEAS_BONE_MASS_LB, 22.05),
    (const.MEAS_BONE_MASS_STONE, 1.57),
    (const.MEAS_HEIGHT_M, 2),
    (const.MEAS_HEIGHT_CM, 200),
    (const.MEAS_HEIGHT_IN, 78.74),
    (const.MEAS_HEIGHT_IMP, '6\' 6"'),
    (const.MEAS_FAT_RATIO_PCT, 7.0),
    (const.MEAS_DIASTOLIC_MMHG, 70),
    (const.MEAS_SYSTOLIC_MMGH, 100),
    (const.MEAS_HEART_PULSE_BPM, 60),
    (const.MEAS_SPO2_PCT, 95.0),
    (const.MEAS_HYDRATION, 0.95),
    (const.MEAS_PWV, 100),
    (const.MEAS_SLEEP_WAKEUP_DURATION_HOURS, 2.7),
    (const.MEAS_SLEEP_LIGHT_DURATION_HOURS, 4.3),
    (const.MEAS_SLEEP_DEEP_DURATION_HOURS, 6.0),
    (const.MEAS_SLEEP_REM_DURATION_HOURS, 7.7),
    (const.MEAS_SLEEP_WAKEUP_DURATION_MINUTES, 160.0),
    (const.MEAS_SLEEP_LIGHT_DURATION_MINUTES, 260.0),
    (const.MEAS_SLEEP_DEEP_DURATION_MINUTES, 360.0),
    (const.MEAS_SLEEP_REM_DURATION_MINUTES, 460.0),
    (const.MEAS_SLEEP_WAKEUP_COUNT, 560.0),
    (const.MEAS_SLEEP_TOSLEEP_DURATION_HOURS, 11.0),
    (const.MEAS_SLEEP_TOWAKEUP_DURATION_HOURS, 12.7),
    (const.MEAS_SLEEP_TOSLEEP_DURATION_MINUTES, 660.0),
    (const.MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES, 760.0),
    (const.MEAS_SLEEP_HEART_RATE_AVERAGE, 860.0),
    (const.MEAS_SLEEP_HEART_RATE_MIN, 960.0),
    (const.MEAS_SLEEP_HEART_RATE_MAX, 1060.0),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE, 1160.0),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MIN, 1260.0),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, 1360.0),
]


@pytest.mark.parametrize('measure,expected', SENSOR_TEST_DATA)
async def test_health_sensor_throttled(
        withings_factory: WithingsFactory,
        measure,
        expected
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(
        measures=measure,
    ))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, 'authorization_code')

    # Checking initial data.
    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )

    # Encountering a throttled data.
    await async_update_entity(
        data.hass,
        get_entity_id(
            measure,
            profile
        )
    )

    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )


NONE_SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, STATE_UNKNOWN),
    (const.MEAS_SLEEP_STATE, STATE_UNKNOWN),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, STATE_UNKNOWN),
]


@pytest.mark.parametrize('measure,expected', NONE_SENSOR_TEST_DATA)
async def test_health_sensor_state_none(
        withings_factory: WithingsFactory,
        measure,
        expected
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(
        measures=measure,
        nokia_measures_response=None,
        nokia_sleep_response=None,
        nokia_sleep_summary_response=None
    ))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, 'authorization_code')

    # Checking initial data.
    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )

    # Encountering a throttled data.
    await async_update_entity(
        data.hass,
        get_entity_id(
            measure,
            profile
        )
    )

    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )


EMPTY_SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, STATE_UNKNOWN),
    (const.MEAS_SLEEP_STATE, STATE_UNKNOWN),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, STATE_UNKNOWN),
]


@pytest.mark.parametrize('measure,expected', EMPTY_SENSOR_TEST_DATA)
async def test_health_sensor_state_empty(
        withings_factory: WithingsFactory,
        measure,
        expected
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(
        measures=measure,
        nokia_measures_response=NokiaMeasures({'measuregrps': []}),
        nokia_sleep_response=NokiaSleep({'series': []}),
        nokia_sleep_summary_response=NokiaSleepSummary({'series': []})
    ))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, 'authorization_code')

    # Checking initial data.
    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )

    # Encountering a throttled data.
    await async_update_entity(
        data.hass,
        get_entity_id(
            measure,
            profile
        )
    )

    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )


SLEEP_STATES_TEST_DATA = [
    (const.STATE_AWAKE, [
        const.MEASURE_TYPE_SLEEP_STATE_DEEP,
        const.MEASURE_TYPE_SLEEP_STATE_AWAKE,
    ]),
    (const.STATE_LIGHT, [
        const.MEASURE_TYPE_SLEEP_STATE_DEEP,
        const.MEASURE_TYPE_SLEEP_STATE_LIGHT,
    ]),
    (const.STATE_REM, [
        const.MEASURE_TYPE_SLEEP_STATE_DEEP,
        const.MEASURE_TYPE_SLEEP_STATE_REM,
    ]),
    (const.STATE_DEEP, [
        const.MEASURE_TYPE_SLEEP_STATE_LIGHT,
        const.MEASURE_TYPE_SLEEP_STATE_DEEP,
    ]),
    (const.STATE_UNKNOWN, [
        const.MEASURE_TYPE_SLEEP_STATE_LIGHT,
        'blah,'
    ])
]


@pytest.mark.parametrize('expected,sleep_states', SLEEP_STATES_TEST_DATA)
async def test_sleep_state_throttled(
        withings_factory: WithingsFactory,
        expected,
        sleep_states
):
    """Test method."""
    measure = const.MEAS_SLEEP_STATE

    data = await withings_factory(WithingsFactoryConfig(
        measures=[measure],
        nokia_sleep_response=nokia_sleep_response(
            sleep_states
        )
    ))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, 'authorization_code')

    # Check initial data.
    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )

    # Encountering a throttled data.
    await async_update_entity(
        data.hass,
        get_entity_id(
            measure,
            profile
        )
    )

    assert_state_equals(
        data.hass,
        profile,
        measure,
        expected
    )


async def test_async_setup_check_credentials(
        hass: HomeAssistantType,
        withings_factory: WithingsFactory
):
    """Test method."""
    check_creds_patch = asynctest.patch(
        'homeassistant.components.withings.common.WithingsDataManager'
        '.check_authenticated',
        side_effect=NotAuthenticatedError()
    )

    async_init_patch = asynctest.patch.object(
        hass.config_entries.flow,
        'async_init',
        wraps=hass.config_entries.flow.async_init
    )

    with check_creds_patch, async_init_patch as async_init_mock:
        data = await withings_factory(WithingsFactoryConfig(
            measures=[
                const.MEAS_HEIGHT_CM
            ]
        ))

        profile = WithingsFactoryConfig.PROFILE_1
        await data.configure_all(profile, 'authorization_code')

        async_init_mock.assert_called_with(
            const.DOMAIN,
            context={
                'source': const.SOURCE_USER,
                const.PROFILE: profile
            },
            data={}
        )


async def test_async_setup_entry_credentials_saver(
        hass: HomeAssistantType
):
    """Test method."""
    expected_creds = {
        'access_token': 'my_access_token2',
        'refresh_token': 'my_refresh_token2',
        'token_type': 'my_token_type2',
        'expires_in': '2',
    }

    original_nokia_api = NokiaApi
    nokia_api_instance = None

    def new_nokia_api(*args, **kwargs):
        nonlocal nokia_api_instance
        nokia_api_instance = original_nokia_api(*args, **kwargs)
        nokia_api_instance.request = MagicMock()
        return nokia_api_instance

    nokia_api_patch = patch('nokia.NokiaApi', side_effect=new_nokia_api)
    session_patch = patch('requests_oauthlib.OAuth2Session')
    client_patch = patch('oauthlib.oauth2.WebApplicationClient')
    update_entry_patch = patch.object(
        hass.config_entries,
        'async_update_entry',
        wraps=hass.config_entries.async_update_entry
    )

    with session_patch, client_patch, nokia_api_patch, update_entry_patch:
        async_add_entities = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        config_entry = ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="my title",
            data={
                const.PROFILE: 'Person 1',
                const.CREDENTIALS: {
                    'access_token': 'my_access_token',
                    'refresh_token': 'my_refresh_token',
                    'token_type': 'my_token_type',
                    'token_expiry': '9999999999',
                },
            },
            source='source',
            connection_class='conn_class'
        )

        await async_setup_entry(hass, config_entry, async_add_entities)

        nokia_api_instance.set_token(expected_creds)

        new_creds = config_entry.data[const.CREDENTIALS].__dict__
        assert new_creds['access_token'] == 'my_access_token2'
