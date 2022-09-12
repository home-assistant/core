"""Configuration for HaFAS tests."""
from datetime import timedelta
import json

from pyhafas.profile import DBProfile
from pyhafas.profile.base.mappings.error_codes import BaseErrorCodesMapping
from pyhafas.types.hafas_response import HafasResponse
import pytest
from requests import Response

import homeassistant.util.dt as dt_util

from .const import (
    TEST_OFFSET,
    TEST_ONLY_DIRECT,
    TEST_STATION1,
    TEST_STATION2,
    TEST_TIME,
)

from tests.common import load_fixture


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock) -> None:
    """Fixture to provide a requests mocker."""
    profile = DBProfile()

    # Mocks the location response for DB HaFAS Station1.
    body = profile.format_location_request(TEST_STATION1)
    data = {"svcReqL": [body]}
    data.update(profile.requestBody)
    data = json.dumps(data)
    url = profile.url_formatter(data)
    requests_mock.post(url, text=load_fixture("station1.json", "hafas"))

    # Mocks the location response for DB HaFAS Station2.
    body = profile.format_location_request(TEST_STATION2)
    data = {"svcReqL": [body]}
    data.update(profile.requestBody)
    data = json.dumps(data)
    url = profile.url_formatter(data)
    requests_mock.post(url, text=load_fixture("station2.json", "hafas"))

    # Mocks the journey response for DB HaFAS between Station1 and Station2.
    station1_res = Response()
    station1_res._content = load_fixture("station1.json", "hafas").encode()
    station1 = profile.parse_location_request(
        HafasResponse(station1_res, BaseErrorCodesMapping)
    )[0]

    station2_res = Response()
    station2_res._content = load_fixture("station2.json", "hafas").encode()
    station2 = profile.parse_location_request(
        HafasResponse(station2_res, BaseErrorCodesMapping)
    )[0]

    date = profile.transform_datetime_parameter_timezone(
        dt_util.as_local(TEST_TIME + timedelta(**TEST_OFFSET))
    )
    body = profile.format_journeys_request(
        station1,
        station2,
        [],
        date,
        0,
        0 if TEST_ONLY_DIRECT else -1,
        {},
        3,
    )
    data = {"svcReqL": [body]}
    data.update(profile.requestBody)
    data = json.dumps(data)
    url = profile.url_formatter(data)
    requests_mock.post(url, text=load_fixture("journey.json", "hafas"))
