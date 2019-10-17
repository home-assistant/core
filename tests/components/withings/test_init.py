"""Tests for the Withings component."""
import re

from asynctest import MagicMock
import responses
import voluptuous as vol
from withings_api import WithingsApi
from withings_api.common import SleepModel, SleepState

import homeassistant.components.api as api
import homeassistant.components.http as http
from homeassistant.components.withings import (
    async_setup,
    async_setup_entry,
    const,
    CONFIG_SCHEMA,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.typing import HomeAssistantType

from .common import (
    WITHINGS_GET_DEVICE_RESPONSE,
    WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
    WITHINGS_SLEEP_RESPONSE,
    WITHINGS_SLEEP_RESPONSE_EMPTY,
    WITHINGS_SLEEP_SUMMARY_RESPONSE,
    WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    WITHINGS_MEASURES_RESPONSE,
    WITHINGS_MEASURES_RESPONSE_EMPTY,
    assert_state_equals,
    configure_integration,
    setup_hass,
    RESPONSES_GET,
)


def config_schema_validate(withings_config) -> None:
    """Assert a schema config succeeds."""
    hass_config = {
        http.DOMAIN: {},
        api.DOMAIN: {"base_url": "http://localhost/"},
        const.DOMAIN: withings_config,
    }

    return CONFIG_SCHEMA(hass_config)


def config_schema_assert_fail(withings_config) -> None:
    """Assert a schema config will fail."""
    try:
        config_schema_validate(withings_config)
        assert False, "This line should not have run."
    except vol.error.MultipleInvalid:
        assert True


def test_config_schema_basic_config() -> None:
    """Test schema."""
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_client_id() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.CLIENT_ID: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.CLIENT_ID: "my_client_id",
            const.PROFILES: ["Person 1"],
        }
    )


def test_config_schema_client_secret() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {const.CLIENT_ID: "my_client_id", const.PROFILES: ["Person 1"]}
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )


def test_config_schema_profiles() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {const.CLIENT_ID: "my_client_id", const.CLIENT_SECRET: "my_client_secret"}
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: "",
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: [],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_base_url() -> None:
    """Test schema."""
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: 123,
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "blah blah",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "https://www.blah.blah.blah/blah/blah",
            const.PROFILES: ["Person 1"],
        }
    )


async def test_async_setup_no_config(hass: HomeAssistantType) -> None:
    """Test method."""
    hass.async_create_task = MagicMock()

    await async_setup(hass, {})

    hass.async_create_task.assert_not_called()


async def test_async_setup_entry_not_authenticated(hass: HomeAssistantType) -> None:
    """Test method."""
    config = await setup_hass(hass)
    profiles = config[const.DOMAIN][const.PROFILES]

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=1,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE_EMPTY,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    # Get the config entry from the previous config flow.
    entries = hass.config_entries.async_entries(const.DOMAIN)

    # Simulate no longer authenticated.
    with responses.RequestsMock() as rsps:
        rsps.add(
            method=RESPONSES_GET,
            url=re.compile(WithingsApi.URL + "/v2/user?.*action=getdevice(&.*)?"),
            status=401,
            json={"status": 100, "body": None},
        )

        # Attempt to setup again with non-authenticated config.
        assert not hass.config_entries.flow.async_progress()
        assert not await async_setup_entry(hass, entries[0])
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert flows
    assert flows[0]["handler"] == const.DOMAIN
    assert flows[0]["context"] == {"source": SOURCE_USER, "profile": profiles[1]}


async def test_full_setup(hass: HomeAssistantType) -> None:
    """Test the whole component lifecycle."""
    config = await setup_hass(hass)
    profiles = config[const.DOMAIN][const.PROFILES]

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=0,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE,
    )

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=1,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE_EMPTY,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=2,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response={
            "status": 0,
            "body": {
                "model": SleepModel.TRACKER.real,
                "series": [
                    {
                        "startdate": "2019-02-01 00:00:00",
                        "enddate": "2019-02-01 01:00:00",
                        "state": SleepState.AWAKE.real,
                    }
                ],
            },
        },
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=3,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response={
            "status": 0,
            "body": {
                "model": SleepModel.TRACKER.real,
                "series": [
                    {
                        "startdate": "2019-02-01 00:00:00",
                        "enddate": "2019-02-01 01:00:00",
                        "state": SleepState.LIGHT.real,
                    }
                ],
            },
        },
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        profiles=profiles,
        profile_index=4,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response={
            "status": 0,
            "body": {
                "model": SleepModel.TRACKER.real,
                "series": [
                    {
                        "startdate": "2019-02-01 00:00:00",
                        "enddate": "2019-02-01 01:00:00",
                        "state": SleepState.REM.real,
                    }
                ],
            },
        },
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    # Test the states of the entities.
    expected_states = (
        (profiles[0], const.MEAS_WEIGHT_KG, 70.0),
        (profiles[0], const.MEAS_FAT_MASS_KG, 5.0),
        (profiles[0], const.MEAS_FAT_FREE_MASS_KG, 60.0),
        (profiles[0], const.MEAS_MUSCLE_MASS_KG, 50.0),
        (profiles[0], const.MEAS_BONE_MASS_KG, 10.0),
        (profiles[0], const.MEAS_HEIGHT_M, 2.0),
        (profiles[0], const.MEAS_FAT_RATIO_PCT, 0.07),
        (profiles[0], const.MEAS_DIASTOLIC_MMHG, 70.0),
        (profiles[0], const.MEAS_SYSTOLIC_MMGH, 100.0),
        (profiles[0], const.MEAS_HEART_PULSE_BPM, 60.0),
        (profiles[0], const.MEAS_SPO2_PCT, 0.95),
        (profiles[0], const.MEAS_HYDRATION, 0.95),
        (profiles[0], const.MEAS_PWV, 100.0),
        (profiles[0], const.MEAS_SLEEP_WAKEUP_DURATION_SECONDS, 320),
        (profiles[0], const.MEAS_SLEEP_LIGHT_DURATION_SECONDS, 520),
        (profiles[0], const.MEAS_SLEEP_DEEP_DURATION_SECONDS, 720),
        (profiles[0], const.MEAS_SLEEP_REM_DURATION_SECONDS, 920),
        (profiles[0], const.MEAS_SLEEP_WAKEUP_COUNT, 1120),
        (profiles[0], const.MEAS_SLEEP_TOSLEEP_DURATION_SECONDS, 1320),
        (profiles[0], const.MEAS_SLEEP_TOWAKEUP_DURATION_SECONDS, 1520),
        (profiles[0], const.MEAS_SLEEP_HEART_RATE_AVERAGE, 1720),
        (profiles[0], const.MEAS_SLEEP_HEART_RATE_MIN, 1920),
        (profiles[0], const.MEAS_SLEEP_HEART_RATE_MAX, 2120),
        (profiles[0], const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE, 2320),
        (profiles[0], const.MEAS_SLEEP_RESPIRATORY_RATE_MIN, 2520),
        (profiles[0], const.MEAS_SLEEP_RESPIRATORY_RATE_MAX, 2720),
        (profiles[0], const.MEAS_SLEEP_STATE, const.STATE_DEEP),
        (profiles[1], const.MEAS_SLEEP_STATE, STATE_UNKNOWN),
        (profiles[1], const.MEAS_HYDRATION, STATE_UNKNOWN),
        (profiles[2], const.MEAS_SLEEP_STATE, const.STATE_AWAKE),
        (profiles[3], const.MEAS_SLEEP_STATE, const.STATE_LIGHT),
        (profiles[3], const.MEAS_FAT_FREE_MASS_KG, STATE_UNKNOWN),
        (profiles[4], const.MEAS_SLEEP_STATE, const.STATE_REM),
    )
    for (profile, meas, value) in expected_states:
        print("CHECKING:", profile, meas, value)
        assert_state_equals(hass, profile, meas, value)

    # Tear down setup entries.
    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)

    await hass.async_block_till_done()
