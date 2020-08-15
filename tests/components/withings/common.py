"""Common data for for the withings component tests."""
import re
import time
from typing import List

import requests_mock
from withings_api import AbstractWithingsApi
from withings_api.common import (
    MeasureGetMeasGroupAttrib,
    MeasureGetMeasGroupCategory,
    MeasureType,
    SleepModel,
    SleepState,
)

from homeassistant import data_entry_flow
import homeassistant.components.api as api
import homeassistant.components.http as http
import homeassistant.components.withings.const as const
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EXTERNAL_URL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify


def get_entity_id(measure, profile) -> str:
    """Get an entity id for a measure and profile."""
    return "sensor.{}_{}_{}".format(const.DOMAIN, measure, slugify(profile))


def assert_state_equals(
    hass: HomeAssistant, profile: str, measure: str, expected
) -> None:
    """Assert the state of a withings sensor."""
    entity_id = get_entity_id(measure, profile)
    state_obj = hass.states.get(entity_id)

    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {measure}, {entity_id}"
    )


async def setup_hass(hass: HomeAssistant) -> dict:
    """Configure Home Assistant."""
    profiles = ["Person0", "Person1", "Person2", "Person3", "Person4"]

    hass_config = {
        "homeassistant": {
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_EXTERNAL_URL: "http://example.local/",
        },
        api.DOMAIN: {},
        http.DOMAIN: {"server_port": 8080},
        const.DOMAIN: {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            const.CONF_PROFILES: profiles,
        },
    }

    await async_process_ha_core_config(hass, hass_config.get("homeassistant"))
    assert await async_setup_component(hass, http.DOMAIN, hass_config)
    assert await async_setup_component(hass, api.DOMAIN, hass_config)
    assert await async_setup_component(hass, const.DOMAIN, hass_config)
    await hass.async_block_till_done()

    return hass_config


async def configure_integration(
    hass: HomeAssistant,
    aiohttp_client,
    aioclient_mock,
    profiles: List[str],
    profile_index: int,
    get_device_response: dict,
    getmeasures_response: dict,
    get_sleep_response: dict,
    get_sleep_summary_response: dict,
) -> None:
    """Configure the integration for a specific profile."""
    selected_profile = profiles[profile_index]

    with requests_mock.mock() as rqmck:
        rqmck.get(
            re.compile(f"{AbstractWithingsApi.URL}/v2/user?.*action=getdevice(&.*|$)"),
            status_code=200,
            json=get_device_response,
        )

        rqmck.get(
            re.compile(f"{AbstractWithingsApi.URL}/v2/sleep?.*action=get(&.*|$)"),
            status_code=200,
            json=get_sleep_response,
        )

        rqmck.get(
            re.compile(
                f"{AbstractWithingsApi.URL}/v2/sleep?.*action=getsummary(&.*|$)"
            ),
            status_code=200,
            json=get_sleep_summary_response,
        )

        rqmck.get(
            re.compile(f"{AbstractWithingsApi.URL}/measure?.*action=getmeas(&.*|$)"),
            status_code=200,
            json=getmeasures_response,
        )

        # Get the withings config flow.
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": SOURCE_USER}
        )
        assert result
        # pylint: disable=protected-access
        state = config_entry_oauth2_flow._encode_jwt(
            hass, {"flow_id": result["flow_id"]}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert result["url"] == (
            "https://account.withings.com/oauth2_user/authorize2?"
            "response_type=code&client_id=my_client_id&"
            "redirect_uri=http://example.local/auth/external/callback&"
            f"state={state}"
            "&scope=user.info,user.metrics,user.activity"
        )

        # Simulate user being redirected from withings site.
        client = await aiohttp_client(hass.http.app)
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        aioclient_mock.post(
            "https://account.withings.com/oauth2/token",
            json={
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": "myuserid",
            },
        )

        # Present user with a list of profiles to choose from.
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result.get("type") == "form"
        assert result.get("step_id") == "profile"
        assert result.get("data_schema").schema["profile"].container == profiles

        # Select the user profile.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {const.PROFILE: selected_profile}
        )

        # Finish the config flow by calling it again.
        assert result.get("type") == "create_entry"
        assert result.get("result")
        config_data = result.get("result").data
        assert config_data.get(const.PROFILE) == profiles[profile_index]
        assert config_data.get("auth_implementation") == const.DOMAIN
        assert config_data.get("token")

        # Ensure all the flows are complete.
        flows = hass.config_entries.flow.async_progress()
        assert not flows

        # Wait for remaining tasks to complete.
        await hass.async_block_till_done()


WITHINGS_GET_DEVICE_RESPONSE_EMPTY = {"status": 0, "body": {"devices": []}}


WITHINGS_GET_DEVICE_RESPONSE = {
    "status": 0,
    "body": {
        "devices": [
            {
                "type": "type1",
                "model": "model1",
                "battery": "battery1",
                "deviceid": "deviceid1",
                "timezone": "UTC",
            }
        ]
    },
}


WITHINGS_MEASURES_RESPONSE_EMPTY = {
    "status": 0,
    "body": {"updatetime": "2019-08-01", "timezone": "UTC", "measuregrps": []},
}


WITHINGS_MEASURES_RESPONSE = {
    "status": 0,
    "body": {
        "updatetime": "2019-08-01",
        "timezone": "UTC",
        "measuregrps": [
            # Un-ambiguous groups.
            {
                "grpid": 1,
                "attrib": MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER.real,
                "date": time.time(),
                "created": time.time(),
                "category": MeasureGetMeasGroupCategory.REAL.real,
                "deviceid": "DEV_ID",
                "more": False,
                "offset": 0,
                "measures": [
                    {"type": MeasureType.WEIGHT, "value": 70, "unit": 0},
                    {"type": MeasureType.FAT_MASS_WEIGHT, "value": 5, "unit": 0},
                    {"type": MeasureType.FAT_FREE_MASS, "value": 60, "unit": 0},
                    {"type": MeasureType.MUSCLE_MASS, "value": 50, "unit": 0},
                    {"type": MeasureType.BONE_MASS, "value": 10, "unit": 0},
                    {"type": MeasureType.HEIGHT, "value": 2, "unit": 0},
                    {"type": MeasureType.TEMPERATURE, "value": 40, "unit": 0},
                    {"type": MeasureType.BODY_TEMPERATURE, "value": 40, "unit": 0},
                    {"type": MeasureType.SKIN_TEMPERATURE, "value": 20, "unit": 0},
                    {"type": MeasureType.FAT_RATIO, "value": 70, "unit": -3},
                    {
                        "type": MeasureType.DIASTOLIC_BLOOD_PRESSURE,
                        "value": 70,
                        "unit": 0,
                    },
                    {
                        "type": MeasureType.SYSTOLIC_BLOOD_PRESSURE,
                        "value": 100,
                        "unit": 0,
                    },
                    {"type": MeasureType.HEART_RATE, "value": 60, "unit": 0},
                    {"type": MeasureType.SP02, "value": 95, "unit": -2},
                    {"type": MeasureType.HYDRATION, "value": 95, "unit": -2},
                    {"type": MeasureType.PULSE_WAVE_VELOCITY, "value": 100, "unit": 0},
                ],
            },
            # Ambiguous groups (we ignore these)
            {
                "grpid": 1,
                "attrib": MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER.real,
                "date": time.time(),
                "created": time.time(),
                "category": MeasureGetMeasGroupCategory.REAL.real,
                "deviceid": "DEV_ID",
                "more": False,
                "offset": 0,
                "measures": [
                    {"type": MeasureType.WEIGHT, "value": 71, "unit": 0},
                    {"type": MeasureType.FAT_MASS_WEIGHT, "value": 4, "unit": 0},
                    {"type": MeasureType.FAT_FREE_MASS, "value": 40, "unit": 0},
                    {"type": MeasureType.MUSCLE_MASS, "value": 51, "unit": 0},
                    {"type": MeasureType.BONE_MASS, "value": 11, "unit": 0},
                    {"type": MeasureType.HEIGHT, "value": 201, "unit": 0},
                    {"type": MeasureType.TEMPERATURE, "value": 41, "unit": 0},
                    {"type": MeasureType.BODY_TEMPERATURE, "value": 34, "unit": 0},
                    {"type": MeasureType.SKIN_TEMPERATURE, "value": 21, "unit": 0},
                    {"type": MeasureType.FAT_RATIO, "value": 71, "unit": -3},
                    {
                        "type": MeasureType.DIASTOLIC_BLOOD_PRESSURE,
                        "value": 71,
                        "unit": 0,
                    },
                    {
                        "type": MeasureType.SYSTOLIC_BLOOD_PRESSURE,
                        "value": 101,
                        "unit": 0,
                    },
                    {"type": MeasureType.HEART_RATE, "value": 61, "unit": 0},
                    {"type": MeasureType.SP02, "value": 98, "unit": -2},
                    {"type": MeasureType.HYDRATION, "value": 96, "unit": -2},
                    {"type": MeasureType.PULSE_WAVE_VELOCITY, "value": 102, "unit": 0},
                ],
            },
        ],
    },
}


WITHINGS_SLEEP_RESPONSE_EMPTY = {
    "status": 0,
    "body": {"model": SleepModel.TRACKER.real, "series": []},
}


WITHINGS_SLEEP_RESPONSE = {
    "status": 0,
    "body": {
        "model": SleepModel.TRACKER.real,
        "series": [
            {
                "startdate": "2019-02-01 00:00:00",
                "enddate": "2019-02-01 01:00:00",
                "state": SleepState.AWAKE.real,
            },
            {
                "startdate": "2019-02-01 01:00:00",
                "enddate": "2019-02-01 02:00:00",
                "state": SleepState.LIGHT.real,
            },
            {
                "startdate": "2019-02-01 02:00:00",
                "enddate": "2019-02-01 03:00:00",
                "state": SleepState.REM.real,
            },
            {
                "startdate": "2019-02-01 03:00:00",
                "enddate": "2019-02-01 04:00:00",
                "state": SleepState.DEEP.real,
            },
        ],
    },
}


WITHINGS_SLEEP_SUMMARY_RESPONSE_EMPTY = {
    "status": 0,
    "body": {"more": False, "offset": 0, "series": []},
}


WITHINGS_SLEEP_SUMMARY_RESPONSE = {
    "status": 0,
    "body": {
        "more": False,
        "offset": 0,
        "series": [
            {
                "timezone": "UTC",
                "model": SleepModel.SLEEP_MONITOR.real,
                "startdate": "2019-02-01",
                "enddate": "2019-02-02",
                "date": "2019-02-02",
                "modified": 12345,
                "data": {
                    "wakeupduration": 110,
                    "lightsleepduration": 210,
                    "deepsleepduration": 310,
                    "remsleepduration": 410,
                    "wakeupcount": 510,
                    "durationtosleep": 610,
                    "durationtowakeup": 710,
                    "hr_average": 810,
                    "hr_min": 910,
                    "hr_max": 1010,
                    "rr_average": 1110,
                    "rr_min": 1210,
                    "rr_max": 1310,
                },
            },
            {
                "timezone": "UTC",
                "model": SleepModel.SLEEP_MONITOR.real,
                "startdate": "2019-02-01",
                "enddate": "2019-02-02",
                "date": "2019-02-02",
                "modified": 12345,
                "data": {
                    "wakeupduration": 210,
                    "lightsleepduration": 310,
                    "deepsleepduration": 410,
                    "remsleepduration": 510,
                    "wakeupcount": 610,
                    "durationtosleep": 710,
                    "durationtowakeup": 810,
                    "hr_average": 910,
                    "hr_min": 1010,
                    "hr_max": 1110,
                    "rr_average": 1210,
                    "rr_min": 1310,
                    "rr_max": 1410,
                },
            },
        ],
    },
}
