"""Tests for the Withings component."""
import re
import time

import requests_mock
import voluptuous as vol
from withings_api import AbstractWithingsApi
from withings_api.common import SleepModel, SleepState

import homeassistant.components.http as http
from homeassistant.components.withings import (
    CONFIG_SCHEMA,
    async_setup,
    async_setup_entry,
    const,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .common import (
    WITHINGS_GET_DEVICE_RESPONSE,
    WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
    WITHINGS_MEASURES_RESPONSE,
    WITHINGS_MEASURES_RESPONSE_EMPTY,
    WITHINGS_SLEEP_RESPONSE,
    WITHINGS_SLEEP_RESPONSE_EMPTY,
    WITHINGS_SLEEP_SUMMARY_RESPONSE,
    WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    assert_state_equals,
    configure_integration,
    setup_hass,
)

from tests.async_mock import MagicMock


def config_schema_validate(withings_config) -> None:
    """Assert a schema config succeeds."""
    hass_config = {http.DOMAIN: {}, const.DOMAIN: withings_config}

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
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_client_id() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_CLIENT_ID: "",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_CLIENT_ID: "my_client_id",
            const.CONF_PROFILES: ["Person 1"],
        }
    )


def test_config_schema_client_secret() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {CONF_CLIENT_ID: "my_client_id", const.CONF_PROFILES: ["Person 1"]}
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1"],
        }
    )


def test_config_schema_profiles() -> None:
    """Test schema."""
    config_schema_assert_fail(
        {CONF_CLIENT_ID: "my_client_id", CONF_CLIENT_SECRET: "my_client_secret"}
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: "",
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: [],
        }
    )
    config_schema_assert_fail(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: ["Person 1", "Person 2"],
        }
    )


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test method."""
    hass.async_create_task = MagicMock()

    await async_setup(hass, {})

    hass.async_create_task.assert_not_called()


async def test_upgrade_token(
    hass: HomeAssistant, aiohttp_client, aioclient_mock
) -> None:
    """Test upgrading from old config data format to new one."""
    config = await setup_hass(hass)
    profiles = config[const.DOMAIN][const.CONF_PROFILES]

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local"},
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
        profiles=profiles,
        profile_index=0,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE_EMPTY,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    entry = entries[0]
    data = entry.data
    token = data.get("token")
    hass.config_entries.async_update_entry(
        entry,
        data={
            const.PROFILE: data.get(const.PROFILE),
            const.CREDENTIALS: {
                "access_token": token.get("access_token"),
                "refresh_token": token.get("refresh_token"),
                "token_expiry": token.get("expires_at"),
                "token_type": token.get("type"),
                "userid": token.get("userid"),
                CONF_CLIENT_ID: token.get("my_client_id"),
                "consumer_secret": token.get("my_consumer_secret"),
            },
        },
    )

    with requests_mock.mock() as rqmck:
        rqmck.get(
            re.compile(f"{AbstractWithingsApi.URL}/v2/user?.*action=getdevice(&.*|$)"),
            status_code=200,
            json=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        )

        assert await async_setup_entry(hass, entry)

    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    data = entries[0].data

    assert data.get("auth_implementation") == const.DOMAIN
    assert data.get("implementation") == const.DOMAIN
    assert data.get(const.PROFILE) == profiles[0]

    token = data.get("token")
    assert token
    assert token.get("access_token") == "mock-access-token"
    assert token.get("refresh_token") == "mock-refresh-token"
    assert token.get("expires_at") > time.time()
    assert token.get("type") == "Bearer"
    assert token.get("userid") == "myuserid"
    assert not token.get(CONF_CLIENT_ID)
    assert not token.get("consumer_secret")


async def test_auth_failure(
    hass: HomeAssistant, aiohttp_client, aioclient_mock
) -> None:
    """Test auth failure."""
    config = await setup_hass(hass)
    profiles = config[const.DOMAIN][const.CONF_PROFILES]

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local"},
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
        profiles=profiles,
        profile_index=0,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE_EMPTY,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    entry = entries[0]
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, **{"new_item": 1}}
    )

    with requests_mock.mock() as rqmck:
        rqmck.get(
            re.compile(f"{AbstractWithingsApi.URL}/v2/user?.*action=getdevice(&.*|$)"),
            status_code=200,
            json={"status": 401, "body": {}},
        )

        assert not (await async_setup_entry(hass, entry))


async def test_full_setup(hass: HomeAssistant, aiohttp_client, aioclient_mock) -> None:
    """Test the whole component lifecycle."""
    config = await setup_hass(hass)
    profiles = config[const.DOMAIN][const.CONF_PROFILES]

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local"},
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
        profiles=profiles,
        profile_index=0,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE,
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
        profiles=profiles,
        profile_index=1,
        get_device_response=WITHINGS_GET_DEVICE_RESPONSE_EMPTY,
        getmeasures_response=WITHINGS_MEASURES_RESPONSE_EMPTY,
        get_sleep_response=WITHINGS_SLEEP_RESPONSE_EMPTY,
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
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
                        "state": SleepState.REM.real,
                    },
                    {
                        "startdate": "2019-02-01 01:00:00",
                        "enddate": "2019-02-01 02:00:00",
                        "state": SleepState.AWAKE.real,
                    },
                ],
            },
        },
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
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
                        "startdate": "2019-02-01 01:00:00",
                        "enddate": "2019-02-01 02:00:00",
                        "state": SleepState.LIGHT.real,
                    },
                    {
                        "startdate": "2019-02-01 00:00:00",
                        "enddate": "2019-02-01 01:00:00",
                        "state": SleepState.REM.real,
                    },
                ],
            },
        },
        get_sleep_summary_response=WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY,
    )

    await configure_integration(
        hass=hass,
        aiohttp_client=aiohttp_client,
        aioclient_mock=aioclient_mock,
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
                        "state": SleepState.LIGHT.real,
                    },
                    {
                        "startdate": "2019-02-01 02:00:00",
                        "enddate": "2019-02-01 03:00:00",
                        "state": SleepState.REM.real,
                    },
                    {
                        "startdate": "2019-02-01 01:00:00",
                        "enddate": "2019-02-01 02:00:00",
                        "state": SleepState.AWAKE.real,
                    },
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
        (profiles[1], const.MEAS_HYDRATION, STATE_UNKNOWN),
        (profiles[3], const.MEAS_FAT_FREE_MASS_KG, STATE_UNKNOWN),
    )
    for (profile, meas, value) in expected_states:
        assert_state_equals(hass, profile, meas, value)

    # Tear down setup entries.
    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)

    await hass.async_block_till_done()
