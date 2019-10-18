"""Common data for for the withings component tests."""
import re
import time
from typing import List

import requests_mock
from withings_api import WithingsApi, WithingsAuth
from withings_api.common import (
    SleepState,
    SleepModel,
    MeasureGetMeasGroupAttrib,
    MeasureGetMeasGroupCategory,
    MeasureType,
)
import homeassistant.components.api as api
import homeassistant.components.http as http
import homeassistant.components.withings.const as const
from homeassistant.util import slugify
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.config_entries import SOURCE_USER
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import async_setup_component
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC


def get_entity_id(measure, profile) -> str:
    """Get an entity id for a measure and profile."""
    return "sensor.{}_{}_{}".format(const.DOMAIN, measure, slugify(profile))


def assert_state_equals(
    hass: HomeAssistantType, profile: str, measure: str, expected
) -> None:
    """Assert the state of a withings sensor."""
    entity_id = get_entity_id(measure, profile)
    state_obj = hass.states.get(entity_id)

    assert state_obj, "Expected entity {} to exist but it did not".format(entity_id)

    assert state_obj.state == str(
        expected
    ), "Expected {} but was {} for measure {}, {}".format(
        expected, state_obj.state, measure, entity_id
    )


async def setup_hass(hass: HomeAssistantType) -> dict:
    """Configure home assistant."""
    profiles = ["Person0", "Person1", "Person2", "Person3", "Person4"]

    hass_config = {
        "homeassistant": {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
        api.DOMAIN: {"base_url": "http://localhost/"},
        http.DOMAIN: {"server_port": 8080},
        const.DOMAIN: {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "https://localhost:8999/",
            const.PROFILES: profiles,
        },
    }

    await async_process_ha_core_config(hass, hass_config.get("homeassistant"))
    assert await async_setup_component(hass, http.DOMAIN, hass_config)
    assert await async_setup_component(hass, api.DOMAIN, hass_config)
    assert await async_setup_component(hass, const.DOMAIN, hass_config)
    await hass.async_block_till_done()

    return hass_config


async def configure_integration(
    hass: HomeAssistantType,
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
        # This will cause the first call to get data to refresh the
        # authentication token before requesting the data. It effectively
        # tests the credential_saver in withings/common.py.
        rqmck.register_uri(
            "POST",
            re.compile(WithingsAuth.URL + "/oauth2/token.*"),
            [
                {
                    "status_code": 200,
                    "json": {
                        "access_token": "my_access_token",
                        "expires_in": 0,
                        "token_type": "Bearer",
                        "scope": "user.info,user.metrics,user.activity",
                        "refresh_token": "my_refresh_token",
                        "userid": "my_user_id",
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "access_token": "my_access_token",
                        "expires_in": 1000,
                        "token_type": "Bearer",
                        "scope": "user.info,user.metrics,user.activity",
                        "refresh_token": "my_refresh_token",
                        "userid": "my_user_id",
                    },
                },
            ],
        )

        rqmck.get(
            re.compile(WithingsApi.URL + "/v2/user?.*action=getdevice(&.*|$)"),
            status_code=200,
            json=get_device_response,
        )

        rqmck.get(
            re.compile(WithingsApi.URL + "/v2/sleep?.*action=get(&.*|$)"),
            status_code=200,
            json=get_sleep_response,
        )

        rqmck.get(
            re.compile(WithingsApi.URL + "/v2/sleep?.*action=getsummary(&.*|$)"),
            status_code=200,
            json=get_sleep_summary_response,
        )

        rqmck.get(
            re.compile(WithingsApi.URL + "/measure?.*action=getmeas(&.*|$)"),
            status_code=200,
            json=getmeasures_response,
        )

        # Get the withings config flow.
        flows = hass.config_entries.flow.async_progress()
        if not flows:
            await hass.config_entries.flow.async_init(
                const.DOMAIN, context={"source": SOURCE_USER}, data={}
            )
        flows = hass.config_entries.flow.async_progress()
        flow = next(flow for flow in flows if flow["handler"] == const.DOMAIN)
        assert flow is not None

        # Present user with a list of profiles to choose from.
        step = await hass.config_entries.flow.async_configure(flow["flow_id"], None)
        assert step["type"] == "form"
        assert step["step_id"] == "user"
        assert step["data_schema"].schema["profile"].container == profiles

        # Select the user profile. Present a form with authorization link.
        step = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {const.PROFILE: selected_profile}
        )
        assert step["step_id"] == "auth"

        # Handle the callback to the hass http endpoint.
        from aiohttp.test_utils import make_mocked_request

        req = make_mocked_request(
            method="GET",
            path="%s?code=%s&profile=%s&flow_id=%s"
            % (
                const.AUTH_CALLBACK_PATH,
                "my_auth_code",
                selected_profile,
                flow["flow_id"],
            ),
            loop=hass.loop,
            app=hass.http.app,
        )
        match_info = await hass.http.app.router.resolve(req)
        response = await match_info.handler(req)
        assert response.text == "<script>window.close()</script>"

        # Finish the config flow by calling it again.
        step = await hass.config_entries.flow.async_configure(flow["flow_id"])
        assert step["type"] == "create_entry"

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
