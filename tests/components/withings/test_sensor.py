"""Tests for the Withings component."""
from unittest.mock import MagicMock, patch

import asynctest
from nokia import NokiaApi, NokiaMeasures, NokiaSleep, NokiaSleepSummary
import pytest

from homeassistant.components.withings import DOMAIN
from homeassistant.components.withings.common import NotAuthenticatedError
import homeassistant.components.withings.const as const
from homeassistant.components.withings.sensor import async_setup_entry
from homeassistant.config_entries import ConfigEntry, SOURCE_USER
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .common import nokia_sleep_response
from .conftest import WithingsFactory, WithingsFactoryConfig


def get_entity_id(measure, profile):
    """Get an entity id for a measure and profile."""
    return "sensor.{}_{}_{}".format(DOMAIN, measure, slugify(profile))


def assert_state_equals(hass: HomeAssistantType, profile: str, measure: str, expected):
    """Assert the state of a withings sensor."""
    entity_id = get_entity_id(measure, profile)
    state_obj = hass.states.get(entity_id)

    assert state_obj, "Expected entity {} to exist but it did not".format(entity_id)

    assert state_obj.state == str(
        expected
    ), "Expected {} but was {} for measure {}".format(
        expected, state_obj.state, measure
    )


async def test_health_sensor_properties(withings_factory: WithingsFactory):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(measures=[const.MEAS_HEIGHT_M]))

    await data.configure_all(WithingsFactoryConfig.PROFILE_1, "authorization_code")

    state = data.hass.states.get("sensor.withings_height_m_person_1")
    state_dict = state.as_dict()
    assert state_dict.get("state") == "2"
    assert state_dict.get("attributes") == {
        "measurement": "height_m",
        "measure_type": 4,
        "friendly_name": "Withings height_m person_1",
        "unit_of_measurement": "m",
        "icon": "mdi:ruler",
    }


SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, 70),
    (const.MEAS_FAT_MASS_KG, 5),
    (const.MEAS_FAT_FREE_MASS_KG, 60),
    (const.MEAS_MUSCLE_MASS_KG, 50),
    (const.MEAS_BONE_MASS_KG, 10),
    (const.MEAS_HEIGHT_M, 2),
    (const.MEAS_FAT_RATIO_PCT, 0.07),
    (const.MEAS_DIASTOLIC_MMHG, 70),
    (const.MEAS_SYSTOLIC_MMGH, 100),
    (const.MEAS_HEART_PULSE_BPM, 60),
    (const.MEAS_SPO2_PCT, 0.95),
    (const.MEAS_HYDRATION, 0.95),
    (const.MEAS_PWV, 100),
    (const.MEAS_SLEEP_WAKEUP_DURATION_SECONDS, 320),
    (const.MEAS_SLEEP_LIGHT_DURATION_SECONDS, 520),
    (const.MEAS_SLEEP_DEEP_DURATION_SECONDS, 720),
    (const.MEAS_SLEEP_REM_DURATION_SECONDS, 920),
    (const.MEAS_SLEEP_WAKEUP_COUNT, 1120),
    (const.MEAS_SLEEP_TOSLEEP_DURATION_SECONDS, 1320),
    (const.MEAS_SLEEP_TOWAKEUP_DURATION_SECONDS, 1520),
    (const.MEAS_SLEEP_HEART_RATE_AVERAGE, 1720),
    (const.MEAS_SLEEP_HEART_RATE_MIN, 1920),
    (const.MEAS_SLEEP_HEART_RATE_MAX, 2120),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE, 2320),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MIN, 2520),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, 2720),
]


@pytest.mark.parametrize("measure,expected", SENSOR_TEST_DATA)
async def test_health_sensor_throttled(
    withings_factory: WithingsFactory, measure, expected
):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(measures=measure))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, "authorization_code")

    # Checking initial data.
    assert_state_equals(data.hass, profile, measure, expected)

    # Encountering a throttled data.
    await async_update_entity(data.hass, get_entity_id(measure, profile))

    assert_state_equals(data.hass, profile, measure, expected)


NONE_SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, STATE_UNKNOWN),
    (const.MEAS_SLEEP_STATE, STATE_UNKNOWN),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, STATE_UNKNOWN),
]


@pytest.mark.parametrize("measure,expected", NONE_SENSOR_TEST_DATA)
async def test_health_sensor_state_none(
    withings_factory: WithingsFactory, measure, expected
):
    """Test method."""
    data = await withings_factory(
        WithingsFactoryConfig(
            measures=measure,
            nokia_measures_response=None,
            nokia_sleep_response=None,
            nokia_sleep_summary_response=None,
        )
    )

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, "authorization_code")

    # Checking initial data.
    assert_state_equals(data.hass, profile, measure, expected)

    # Encountering a throttled data.
    await async_update_entity(data.hass, get_entity_id(measure, profile))

    assert_state_equals(data.hass, profile, measure, expected)


EMPTY_SENSOR_TEST_DATA = [
    (const.MEAS_WEIGHT_KG, STATE_UNKNOWN),
    (const.MEAS_SLEEP_STATE, STATE_UNKNOWN),
    (const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, STATE_UNKNOWN),
]


@pytest.mark.parametrize("measure,expected", EMPTY_SENSOR_TEST_DATA)
async def test_health_sensor_state_empty(
    withings_factory: WithingsFactory, measure, expected
):
    """Test method."""
    data = await withings_factory(
        WithingsFactoryConfig(
            measures=measure,
            nokia_measures_response=NokiaMeasures({"measuregrps": []}),
            nokia_sleep_response=NokiaSleep({"series": []}),
            nokia_sleep_summary_response=NokiaSleepSummary({"series": []}),
        )
    )

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, "authorization_code")

    # Checking initial data.
    assert_state_equals(data.hass, profile, measure, expected)

    # Encountering a throttled data.
    await async_update_entity(data.hass, get_entity_id(measure, profile))

    assert_state_equals(data.hass, profile, measure, expected)


SLEEP_STATES_TEST_DATA = [
    (
        const.STATE_AWAKE,
        [const.MEASURE_TYPE_SLEEP_STATE_DEEP, const.MEASURE_TYPE_SLEEP_STATE_AWAKE],
    ),
    (
        const.STATE_LIGHT,
        [const.MEASURE_TYPE_SLEEP_STATE_DEEP, const.MEASURE_TYPE_SLEEP_STATE_LIGHT],
    ),
    (
        const.STATE_REM,
        [const.MEASURE_TYPE_SLEEP_STATE_DEEP, const.MEASURE_TYPE_SLEEP_STATE_REM],
    ),
    (
        const.STATE_DEEP,
        [const.MEASURE_TYPE_SLEEP_STATE_LIGHT, const.MEASURE_TYPE_SLEEP_STATE_DEEP],
    ),
    (const.STATE_UNKNOWN, [const.MEASURE_TYPE_SLEEP_STATE_LIGHT, "blah,"]),
]


@pytest.mark.parametrize("expected,sleep_states", SLEEP_STATES_TEST_DATA)
async def test_sleep_state_throttled(
    withings_factory: WithingsFactory, expected, sleep_states
):
    """Test method."""
    measure = const.MEAS_SLEEP_STATE

    data = await withings_factory(
        WithingsFactoryConfig(
            measures=[measure], nokia_sleep_response=nokia_sleep_response(sleep_states)
        )
    )

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, "authorization_code")

    # Check initial data.
    assert_state_equals(data.hass, profile, measure, expected)

    # Encountering a throttled data.
    await async_update_entity(data.hass, get_entity_id(measure, profile))

    assert_state_equals(data.hass, profile, measure, expected)


async def test_async_setup_check_credentials(
    hass: HomeAssistantType, withings_factory: WithingsFactory
):
    """Test method."""
    check_creds_patch = asynctest.patch(
        "homeassistant.components.withings.common.WithingsDataManager"
        ".check_authenticated",
        side_effect=NotAuthenticatedError(),
    )

    async_init_patch = asynctest.patch.object(
        hass.config_entries.flow,
        "async_init",
        wraps=hass.config_entries.flow.async_init,
    )

    with check_creds_patch, async_init_patch as async_init_mock:
        data = await withings_factory(
            WithingsFactoryConfig(measures=[const.MEAS_HEIGHT_M])
        )

        profile = WithingsFactoryConfig.PROFILE_1
        await data.configure_all(profile, "authorization_code")

        async_init_mock.assert_called_with(
            const.DOMAIN,
            context={"source": SOURCE_USER, const.PROFILE: profile},
            data={},
        )


async def test_async_setup_entry_credentials_saver(hass: HomeAssistantType):
    """Test method."""
    expected_creds = {
        "access_token": "my_access_token2",
        "refresh_token": "my_refresh_token2",
        "token_type": "my_token_type2",
        "expires_in": "2",
    }

    original_nokia_api = NokiaApi
    nokia_api_instance = None

    def new_nokia_api(*args, **kwargs):
        nonlocal nokia_api_instance
        nokia_api_instance = original_nokia_api(*args, **kwargs)
        nokia_api_instance.request = MagicMock()
        return nokia_api_instance

    nokia_api_patch = patch("nokia.NokiaApi", side_effect=new_nokia_api)
    session_patch = patch("requests_oauthlib.OAuth2Session")
    client_patch = patch("oauthlib.oauth2.WebApplicationClient")
    update_entry_patch = patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    )

    with session_patch, client_patch, nokia_api_patch, update_entry_patch:
        async_add_entities = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        config_entry = ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="my title",
            data={
                const.PROFILE: "Person 1",
                const.CREDENTIALS: {
                    "access_token": "my_access_token",
                    "refresh_token": "my_refresh_token",
                    "token_type": "my_token_type",
                    "token_expiry": "9999999999",
                },
            },
            source="source",
            connection_class="conn_class",
            system_options={},
        )

        await async_setup_entry(hass, config_entry, async_add_entities)

        nokia_api_instance.set_token(expected_creds)

        new_creds = config_entry.data[const.CREDENTIALS]
        assert new_creds["access_token"] == "my_access_token2"
