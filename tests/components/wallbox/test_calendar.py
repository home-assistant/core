"""Test Wallbox calendar component."""

import datetime

from freezegun.api import FrozenDateTimeFactory
import requests_mock

from homeassistant.components.calendar import (
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import (
    authorisation_response,
    setup_integration,
    setup_integration_no_sessions,
    test_response_sessions,
    test_response_sessions_empty,
)

from tests.common import MockConfigEntry


async def test_calendar(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Test for successfully setting up the Wallbox calendar."""
    await setup_integration(hass, entry)
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions,
            status_code=200,
        )

        await hass.services.async_call(
            "calendar",
            SERVICE_GET_EVENTS,
            {
                ATTR_ENTITY_ID: ["calendar.wallbox_wallboxname"],
                EVENT_START_DATETIME: dt_util.now() - datetime.timedelta(days=30),
                EVENT_END_DATETIME: dt_util.now(),
            },
            blocking=True,
            return_response=True,
        )


async def test_calendar_empty(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Test for successfully setting up the Wallbox calendar."""
    await setup_integration_no_sessions(hass, entry)
    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/v4/sessions/stats",
            json=test_response_sessions_empty,
            status_code=200,
        )

        await hass.services.async_call(
            "calendar",
            SERVICE_GET_EVENTS,
            {
                ATTR_ENTITY_ID: ["calendar.wallbox_wallboxname"],
                EVENT_START_DATETIME: dt_util.now() - datetime.timedelta(days=30),
                EVENT_END_DATETIME: dt_util.now(),
            },
            blocking=True,
            return_response=True,
        )
