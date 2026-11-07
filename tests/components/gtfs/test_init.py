"""Tests for GTFS config entry setup and removal."""

from typing import Any
from unittest.mock import patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gtfs.const import CONF_DATABASE, DOMAIN
from homeassistant.components.gtfs.feed import close_feed, feed_database_path
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import (
    FEED_URL,
    ROUTE_ENTITY_ID,
    ROUTE_SUBENTRY_ID,
    TEST_DATABASE,
    build_feed_zip,
    gtfs_files,
    setup_integration,
)


@pytest.mark.usefixtures("mock_feed_download")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the feed is imported on setup and released on unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert gtfs_files(hass) == [TEST_DATABASE]
    feed = mock_config_entry.runtime_data

    with patch("homeassistant.components.gtfs.close_feed", wraps=close_feed) as close:
        await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    close.assert_called_once_with(feed)


async def test_existing_database_is_reused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_feed_download: AiohttpClientMocker,
) -> None:
    """Test a reload does not download the feed again."""
    await setup_integration(hass, mock_config_entry)
    assert mock_feed_download.call_count == 1

    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_feed_download.call_count == 1


async def test_missing_database_is_downloaded_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_feed_download: AiohttpClientMocker,
) -> None:
    """Test setup downloads the feed again when the cached database is gone.

    The cache folder is left out of backups, so this is what a restore looks like.
    """
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    feed_database_path(hass, TEST_DATABASE).unlink()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_feed_download.call_count == 2
    assert gtfs_files(hass) == [TEST_DATABASE]


@pytest.mark.usefixtures("mock_feed_download")
async def test_removing_route_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a route reloads the entry and removes its entity and device."""
    await setup_integration(hass, mock_config_entry)
    feed = mock_config_entry.runtime_data
    assert entity_registry.async_get(ROUTE_ENTITY_ID) is not None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, ROUTE_SUBENTRY_ID), mock_config_entry.entry_id
        )
        is not None
    )

    hass.config_entries.async_remove_subentry(mock_config_entry, ROUTE_SUBENTRY_ID)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not feed
    assert entity_registry.async_get(ROUTE_ENTITY_ID) is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, ROUTE_SUBENTRY_ID), mock_config_entry.entry_id
        )
        is None
    )


@pytest.mark.parametrize(
    ("response", "state"),
    [
        pytest.param(
            {"exc": ClientError(FEED_URL)},
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
        pytest.param(
            {"text": "<html></html>"}, ConfigEntryState.SETUP_ERROR, id="invalid_feed"
        ),
        pytest.param(
            {"content": build_feed_zip(exclude=frozenset({"stops.txt"}))},
            ConfigEntryState.SETUP_ERROR,
            id="missing_file",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    state: ConfigEntryState,
) -> None:
    """Test an unusable feed fails setup, retrying only if it was unreachable."""
    aioclient_mock.get(FEED_URL, **response)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
    assert gtfs_files(hass) == []
    assert mock_config_entry.reason is not None
    assert FEED_URL not in mock_config_entry.reason


@pytest.mark.usefixtures("mock_feed_download")
async def test_remove_entry_deletes_database(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test removing the entry deletes its feed database."""
    await setup_integration(hass, mock_config_entry)
    assert feed_database_path(hass, TEST_DATABASE).exists()

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert gtfs_files(hass) == []


@pytest.mark.usefixtures("mock_feed_download")
async def test_download_written_in_chunks(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a feed spanning several write buffers is downloaded intact."""
    with patch("homeassistant.components.gtfs.feed.CHUNK_SIZE", 100):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert gtfs_files(hass) == [TEST_DATABASE]


CALENDAR_HEADER = (
    "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
    "start_date,end_date\n"
)
CALENDAR_DATES_HEADER = "service_id,date,exception_type\n"


def _expired_issue(
    issue_registry: ir.IssueRegistry, entry: MockConfigEntry
) -> ir.IssueEntry | None:
    return issue_registry.async_get_issue(DOMAIN, f"feed_expired_{entry.entry_id}")


ADDED_DATES = f"{CALENDAR_DATES_HEADER}DAILY,20280115,1\nDAILY,20280301,2\n"


@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    ("feed_zip", "now", "last_date"),
    [
        pytest.param(
            build_feed_zip(), "2028-01-01 00:01:00", "2027-12-31", id="calendar_ended"
        ),
        pytest.param(
            build_feed_zip(
                exclude=frozenset({"calendar.txt"}),
                replace={"calendar_dates.txt": ADDED_DATES},
            ),
            "2028-01-16 12:00:00",
            "2028-01-15",
            id="added_dates_ended",
        ),
    ],
)
async def test_expired_feed_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    now: str,
    last_date: str,
) -> None:
    """Test an issue is raised at setup when the feed has no service left."""
    freezer.move_to(f"{now}-05:00")
    await setup_integration(hass, mock_config_entry)

    assert (issue := _expired_issue(issue_registry, mock_config_entry)) is not None
    assert issue.translation_key == "feed_expired"
    assert issue.translation_placeholders == {
        "title": "Test Agency",
        "last_date": last_date,
    }


@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    ("feed_zip", "now"),
    [
        pytest.param(build_feed_zip(), "2027-12-31 23:59:00", id="last_day"),
        pytest.param(
            build_feed_zip(replace={"calendar_dates.txt": ADDED_DATES}),
            "2028-01-10 12:00:00",
            id="added_date_ahead",
        ),
        pytest.param(
            build_feed_zip(
                exclude=frozenset({"calendar.txt"}),
                replace={"calendar_dates.txt": CALENDAR_DATES_HEADER},
            ),
            "2028-01-16 12:00:00",
            id="no_service_dates",
        ),
    ],
)
async def test_feed_not_expired(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    now: str,
) -> None:
    """Test no issue is raised while the feed has service left or no dates at all."""
    freezer.move_to(f"{now}-05:00")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _expired_issue(issue_registry, mock_config_entry) is None


@pytest.mark.usefixtures("mock_feed_download")
async def test_expired_feed_issue_raised_at_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the issue is raised once the last service day ends and cleared on unload."""
    freezer.move_to("2027-12-31 23:59:00-05:00")
    await setup_integration(hass, mock_config_entry)
    assert _expired_issue(issue_registry, mock_config_entry) is None

    freezer.move_to("2028-01-01 00:00:00-05:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _expired_issue(issue_registry, mock_config_entry) is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert _expired_issue(issue_registry, mock_config_entry) is None


async def test_expired_feed_issue_cleared_by_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    feed_zip: bytes,
) -> None:
    """Test downloading a feed with a new timetable clears the issue."""
    freezer.move_to("2028-01-02 12:00:00-05:00")
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await setup_integration(hass, mock_config_entry)
    assert _expired_issue(issue_registry, mock_config_entry) is not None

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        FEED_URL,
        content=build_feed_zip(
            replace={
                "calendar.txt": f"{CALENDAR_HEADER}DAILY,1,1,1,1,1,1,1,20280101,20281231\n"
            }
        ),
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: FEED_URL}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_DATABASE] != TEST_DATABASE
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _expired_issue(issue_registry, mock_config_entry) is None
