"""Test the Open Home Foundation Events calendar."""

from datetime import timedelta
from http import HTTPStatus

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.open_home_foundation_events.const import API_URL
from homeassistant.components.open_home_foundation_events.coordinator import (
    SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

ENTITY_ID = "calendar.dublin"


@pytest.mark.freeze_time("2026-10-08T12:00:00+00:00")
async def test_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the calendar shows the next event within the area."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dublin Meetup"
    assert state.attributes["location"] == (
        "26 Wexford St, Portobello, Dublin, D02 HX93, Ireland"
    )
    assert len(mock_api.mock_calls) == 1

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "dublin-subentry-id"
    assert entry.config_subentry_id == "dublin-subentry-id"
    assert device_registry.async_get_device_by_identifier(
        ("open_home_foundation_events", "dublin-subentry-id"),
        mock_config_entry.entry_id,
    )


@pytest.mark.freeze_time("2026-10-20T18:00:00+00:00")
async def test_calendar_event_in_progress(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the calendar is on during an event."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.freeze_time("2026-10-08T12:00:00+00:00")
async def test_get_events(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test only non-cancelled, located events within the radius are returned."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{ENTITY_ID}?start=2026-10-01T00:00:00Z&end=2026-12-01T00:00:00Z"
    )

    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert [event["summary"] for event in events] == [
        "Dublin Meetup",
        "Dublin Open Evening",
    ]
    assert events[0]["uid"] == "evt-dublin@events.lu.ma"


@pytest.mark.freeze_time("2026-10-08T12:00:00+00:00")
@pytest.mark.parametrize(
    ("radius_area", "summaries"),
    [
        (
            {"latitude": 53.3498, "longitude": -6.2603, "radius": 200000},
            ["Dublin Meetup", "Dublin Open Evening", "Galway Meetup"],
        ),
        (
            {"latitude": 50.9375, "longitude": 6.9603, "radius": 50000},
            ["Hürth Meetup"],
        ),
    ],
    ids=["ireland", "cologne"],
)
async def test_area_filtering(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    radius_area: dict[str, float],
    summaries: list[str],
) -> None:
    """Test the area decides which events are shown."""
    mock_config_entry.add_to_hass(hass)
    subentry = mock_config_entry.subentries["dublin-subentry-id"]
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data=radius_area
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{ENTITY_ID}?start=2026-10-01T00:00:00Z&end=2026-12-01T00:00:00Z"
    )

    events = await response.json()
    assert [event["summary"] for event in events] == summaries


async def test_setup_retry_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the entry is retried when the API is unreachable."""
    aioclient_mock.get(API_URL, exc=ClientError)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="invalid_json"),
        pytest.param('[{"calendar": "x"}]', id="missing_events"),
        pytest.param(
            '[{"events": [{"id": "a", "summary": "b", "start": "nope",'
            ' "latitude": 1, "longitude": 1}]}]',
            id="invalid_start",
        ),
    ],
)
async def test_setup_retry_on_invalid_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    payload: str,
) -> None:
    """Test the entry is retried when the API returns something unexpected."""
    aioclient_mock.get(API_URL, text=payload)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unavailable_on_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the calendar becomes unavailable when an update fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    mock_api.clear_requests()
    mock_api.get(API_URL, exc=ClientError)
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test unloading the entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.freeze_time("2026-10-08T12:00:00+00:00")
async def test_area_change_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test changing an area updates its calendar."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["message"] == "Dublin Meetup"

    hass.config_entries.async_update_subentry(
        mock_config_entry,
        mock_config_entry.subentries["dublin-subentry-id"],
        data={"latitude": 50.9375, "longitude": 6.9603, "radius": 50000},
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["message"] == "Hürth Meetup"
