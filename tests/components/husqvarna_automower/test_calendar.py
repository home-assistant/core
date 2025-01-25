"""Tests for calendar platform."""

from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock
import urllib
import zoneinfo

from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)
from tests.typing import ClientSessionGenerator

TEST_ENTITY = "calendar.test_mower_1"
type GetEventsFn = Callable[[str, str], Awaitable[dict[str, Any]]]


@pytest.fixture(name="get_events")
def get_events_fixture(
    hass_client: ClientSessionGenerator,
) -> GetEventsFn:
    """Fetch calendar events from the HTTP API."""

    async def _fetch(start: str, end: str) -> list[dict[str, Any]]:
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{TEST_ENTITY}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"
        )
        assert response.status == HTTPStatus.OK
        results = await response.json()
        return [{k: event[k] for k in ("summary", "start", "end")} for event in results]

    return _fetch


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5, 12))
async def test_calendar_state_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State test of the calendar."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("calendar.test_mower_1")
    assert state is not None
    assert state.state == "off"


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5, 19))
async def test_calendar_state_on(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State test of the calendar."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("calendar.test_mower_1")
    assert state is not None
    assert state.state == "on"


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5))
async def test_empty_calendar(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    get_events: GetEventsFn,
    mower_time_zone: zoneinfo.ZoneInfo,
) -> None:
    """State if there is no schedule set."""
    await setup_integration(hass, mock_config_entry)
    json_values = load_json_value_fixture("mower.json", DOMAIN)
    json_values["data"][0]["attributes"]["calendar"]["tasks"] = []
    values = mower_list_to_dictionary_dataclass(
        json_values,
        mower_time_zone,
    )
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("calendar.test_mower_1")
    assert state is not None
    assert state.state == "off"
    events = await get_events("2023-06-05T00:00:00", "2023-06-12T00:00:00")
    assert events == []


@pytest.mark.freeze_time(datetime.datetime(2023, 6, 5))
@pytest.mark.parametrize(
    (
        "start_date",
        "end_date",
    ),
    [
        (
            datetime.datetime(2023, 6, 5, tzinfo=datetime.UTC),
            datetime.datetime(2023, 6, 12, tzinfo=datetime.UTC),
        ),
    ],
)
async def test_calendar_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    start_date: datetime,
    end_date: datetime,
) -> None:
    """Snapshot test of the calendar entity."""
    await setup_integration(hass, mock_config_entry)
    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ["calendar.test_mower_1", "calendar.test_mower_2"],
            EVENT_START_DATETIME: start_date,
            EVENT_END_DATETIME: end_date,
        },
        blocking=True,
        return_response=True,
    )

    assert events == snapshot
