"""Tests for the GTFS config flow."""

from contextlib import AbstractContextManager
import json
import logging
from pathlib import Path
import threading
from typing import Any
from unittest.mock import ANY, AsyncMock, patch
import zipfile

from aiohttp import ClientError
import pygtfs
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from sqlalchemy.exc import OperationalError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gtfs.const import (
    CONF_DATABASE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    DEFAULT_PATH,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from homeassistant.components.gtfs.feed import (
    async_fetch_feed,
    feed_database_path,
    import_feed,
    list_stops,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    FEED_URL,
    ROUTE_ENTITY_ID,
    ROUTE_SUBENTRY_ID,
    TEST_DATABASE,
    build_feed_zip,
    gtfs_files,
    setup_integration,
)

AGENCY_HEADER = "agency_id,agency_name,agency_url,agency_timezone\n"
STOP_TIMES_HEADER = "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
NEW_FEED_URL = "https://example.com/new/gtfs.zip"
OTHER_FEED_URL = "https://example.org/gtfs.zip"
# The fixture feed plus a Fourth Street stop, to tell the feeds apart.
NEW_FEED_ZIP = build_feed_zip(
    replace={
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,First Street,40.0,-75.0\n"
            "S2,Second Street,40.01,-75.01\n"
            "S3,Third Street,40.02,-75.02\n"
            "S4,Fourth Street,40.03,-75.03\n"
            "N1,Night Depot,40.1,-75.1\n"
            "N2,Night Terminal,40.11,-75.11\n"
        )
    }
)


async def _start_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return result["flow_id"]


async def _submit_url(hass: HomeAssistant, flow_id: str) -> ConfigFlowResult:
    """Submit FEED_URL and return the result once the feed has loaded."""
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


def _assert_load_error(
    hass: HomeAssistant, result: ConfigFlowResult, error: str
) -> None:
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_URL) == FEED_URL
    )
    assert gtfs_files(hass) == []


async def _assert_recovers(hass: HomeAssistant, flow_id: str) -> None:
    result = await _submit_url(hass, flow_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert gtfs_files(hass) == [result["data"][CONF_DATABASE]]


@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    ("feed_zip", "title"),
    [
        pytest.param(build_feed_zip(), "Test Agency", id="agency_name"),
        pytest.param(
            build_feed_zip(
                replace={
                    "agency.txt": (
                        f"{AGENCY_HEADER}TA,,https://example.com,America/New_York\n"
                    )
                }
            ),
            "example.com",
            id="host_fallback",
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, title: str
) -> None:
    """Test adding a feed by URL, titled by its agency or else the URL host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "load_feed"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {CONF_URL: FEED_URL, CONF_DATABASE: ANY}
    assert result["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1

    # Let any cleanup scheduled when the flow was removed run.
    await hass.async_block_till_done()
    db_path = feed_database_path(hass, result["data"][CONF_DATABASE])
    assert db_path.is_file()
    assert db_path.parent == Path(hass.config.cache_path(DOMAIN))
    assert sorted(path.name for path in db_path.parent.iterdir()) == [db_path.name]
    # YAML users keep their feeds in config/gtfs; the flow never writes there.
    assert not Path(hass.config.path(DEFAULT_PATH)).exists()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("response", "error"),
    [
        pytest.param({"exc": ClientError()}, "cannot_connect", id="connection_error"),
        pytest.param({"exc": TimeoutError()}, "cannot_connect", id="timeout"),
        pytest.param({"status": 500}, "cannot_connect", id="server_error"),
        pytest.param({"text": "<html>Not here</html>"}, "invalid_feed", id="html_page"),
        pytest.param(
            {"content": build_feed_zip(exclude=frozenset({"stops.txt"}))},
            "invalid_feed",
            id="missing_stops",
        ),
        pytest.param(
            {
                "content": build_feed_zip(
                    exclude=frozenset({"calendar.txt", "calendar_dates.txt"})
                )
            },
            "invalid_feed",
            id="missing_calendar",
        ),
        pytest.param(
            {"content": build_feed_zip(replace={"agency.txt": AGENCY_HEADER})},
            "invalid_feed",
            id="no_agency",
        ),
        pytest.param(
            {
                "content": build_feed_zip(
                    replace={"agency.txt": AGENCY_HEADER.encode() + b"TA,\xff\n"}
                )
            },
            "invalid_feed",
            id="agency_not_utf8",
        ),
        pytest.param(
            {
                "content": build_feed_zip(
                    replace={"stop_times.txt": f"{STOP_TIMES_HEADER}T1,8:xx:00,,S1,1\n"}
                )
            },
            "invalid_feed",
            id="malformed_stop_time",
        ),
        pytest.param(
            {"content": build_feed_zip(replace={"calendar.txt": b""})},
            "invalid_feed",
            id="empty_file",
        ),
        pytest.param(
            {
                "content": build_feed_zip(
                    replace={
                        "stops.txt": (
                            "stop_id,stop_name,stop_lat,stop_lon\n"
                            "S1,First Street,40.0,-75.0\n"
                            "S1,First Street Again,40.0,-75.0\n"
                        )
                    }
                )
            },
            "invalid_feed",
            id="duplicate_stop",
        ),
    ],
)
async def test_user_flow_download_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    feed_zip: bytes,
    response: dict[str, Any],
    error: str,
) -> None:
    """Test feeds that fail to load return to the form, which can then recover."""
    aioclient_mock.get(FEED_URL, **response)
    flow_id = await _start_flow(hass)

    _assert_load_error(hass, await _submit_url(hass, flow_id), error)

    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await _assert_recovers(hass, flow_id)


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"exc": ClientError(FEED_URL)}, id="connection_error"),
        pytest.param({"status": 401}, id="server_error"),
    ],
)
async def test_user_flow_download_error_not_logging_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    feed_zip: bytes,
    response: dict[str, Any],
) -> None:
    """Test a failed download is logged without the URL, which may hold a token."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.gtfs")
    aioclient_mock.get(FEED_URL, **response)
    flow_id = await _start_flow(hass)

    _assert_load_error(hass, await _submit_url(hass, flow_id), "cannot_connect")

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("homeassistant.components.gtfs")
    ]
    assert any("Could not download GTFS feed" in message for message in messages)
    assert not any("example.com" in message for message in messages)

    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await _assert_recovers(hass, flow_id)


@pytest.mark.usefixtures("mock_feed_download", "mock_setup_entry")
@pytest.mark.parametrize(
    ("patcher", "error"),
    [
        pytest.param(
            patch.object(zipfile.ZipFile, "open", side_effect=zipfile.BadZipFile),
            "invalid_feed",
            id="bad_zip",
        ),
        pytest.param(
            patch.object(zipfile.ZipFile, "open", side_effect=NotImplementedError),
            "invalid_feed",
            id="unsupported_compression",
        ),
        pytest.param(
            patch.object(zipfile.ZipFile, "open", side_effect=RuntimeError),
            "invalid_feed",
            id="encrypted",
        ),
        pytest.param(
            patch(
                "homeassistant.components.gtfs.feed.pygtfs.append_feed",
                side_effect=OperationalError("stmt", {}, Exception("disk full")),
            ),
            "unknown",
            id="database_error",
        ),
        pytest.param(
            patch(
                "homeassistant.components.gtfs.config_flow.async_fetch_feed",
                side_effect=RuntimeError,
            ),
            "unknown",
            id="unexpected_error",
        ),
    ],
)
async def test_user_flow_load_errors(
    hass: HomeAssistant, patcher: AbstractContextManager[Any], error: str
) -> None:
    """Test load failures that need a patch to force return to the form."""
    flow_id = await _start_flow(hass)

    with patcher:
        result = await _submit_url(hass, flow_id)
    _assert_load_error(hass, result, error)

    await _assert_recovers(hass, flow_id)


@pytest.mark.usefixtures("mock_feed_download", "mock_setup_entry")
@pytest.mark.parametrize(
    "url",
    [
        pytest.param("ftp://example.com/gtfs.zip", id="ftp"),
        pytest.param("http://", id="no_host"),
        pytest.param("not a url", id="relative"),
        pytest.param("http://[::1", id="unparsable"),
    ],
)
async def test_user_flow_invalid_url(hass: HomeAssistant, url: str) -> None:
    """Test a URL that is not http or https is rejected before downloading."""
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_URL: url})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "invalid_url"}
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_URL) == url

    await _assert_recovers(hass, flow_id)


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a URL that is already configured aborts, ignoring whitespace."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: f"  {FEED_URL}  "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert gtfs_files(hass) == []


@pytest.mark.usefixtures("mock_feed_download")
async def test_user_flow_duplicate_finished_first(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the import is discarded if the URL was configured while it ran."""
    flow_id = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()
    assert len(gtfs_files(hass)) == 1

    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Flow removal deletes the database in a background executor job.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert gtfs_files(hass) == []


@pytest.mark.usefixtures("mock_feed_download")
async def test_user_flow_aborted_during_import(hass: HomeAssistant) -> None:
    """Test aborting the flow mid-import discards the imported database."""
    append_feed = pygtfs.append_feed
    appended = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    cancel_events: list[threading.Event] = []

    async def recording_fetch_feed(
        hass: HomeAssistant, url: str, db_path: Path, cancelled: threading.Event
    ) -> str | None:
        cancel_events.append(cancelled)
        return await async_fetch_feed(hass, url, db_path, cancelled)

    # Block after appending so the import has a database to discard.
    def blocking_append_feed(schedule: pygtfs.Schedule, feed_filename: str) -> None:
        append_feed(schedule, feed_filename)
        appended.set()
        release.wait(10)

    def signalling_import_feed(
        zip_path: Path, db_path: Path, cancelled: threading.Event
    ) -> None:
        try:
            import_feed(zip_path, db_path, cancelled)
        finally:
            finished.set()

    with (
        patch(
            "homeassistant.components.gtfs.feed.pygtfs.append_feed",
            blocking_append_feed,
        ),
        patch("homeassistant.components.gtfs.feed.import_feed", signalling_import_feed),
        patch(
            "homeassistant.components.gtfs.config_flow.async_fetch_feed",
            recording_fetch_feed,
        ),
    ):
        flow_id = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_URL: FEED_URL}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert await hass.async_add_executor_job(appended.wait, 10)

        try:
            hass.config_entries.flow.async_abort(flow_id)
            # Set before the task's cancellation is delivered, which can be
            # after the database unlink is scheduled.
            assert [event.is_set() for event in cancel_events] == [True]
            await hass.async_block_till_done()
            # The download is cleaned up while the import thread is still running.
            assert [Path(name).suffix for name in gtfs_files(hass)] == [".tmp"]
        finally:
            release.set()
        assert await hass.async_add_executor_job(finished.wait, 10)

    assert gtfs_files(hass) == []


def test_import_cancelled_after_swap(tmp_path: Path) -> None:
    """Test a cancellation that arrives during the swap discards the database."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    zip_path = work_dir / "feed.zip"
    zip_path.write_bytes(build_feed_zip())
    db_path = work_dir / "feed.sqlite"
    cancelled = threading.Event()
    replace = Path.replace

    def replace_then_cancel(self: Path, target: Path) -> Path:
        result = replace(self, target)
        cancelled.set()
        return result

    with patch.object(Path, "replace", replace_then_cancel):
        import_feed(zip_path, db_path, cancelled)

    assert list(work_dir.iterdir()) == [zip_path]


@pytest.mark.usefixtures("mock_feed_download")
async def test_user_flow_removed_before_finish(hass: HomeAssistant) -> None:
    """Test removing the flow after the import but before finishing deletes it."""
    flow_id = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    assert len(gtfs_files(hass)) == 1

    hass.config_entries.flow.async_abort(flow_id)
    # Flow removal deletes the database in a background executor job.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert gtfs_files(hass) == []


async def _start_route_flow(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ROUTE), context={"source": SOURCE_USER}
    )
    return result["flow_id"]


def _route_input(origin: str, destination: str) -> dict[str, str]:
    return {CONF_ORIGIN: origin, CONF_DESTINATION: destination}


@pytest.mark.usefixtures("mock_feed_download")
async def test_add_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test adding a route titled from its stop names."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ROUTE),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ORIGIN].config["options"] == snapshot

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _route_input("S2", "S3")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Second Street to Third Street"
    assert result["data"] == {CONF_ORIGIN: "S2", CONF_DESTINATION: "S3"}
    assert result["unique_id"] == json.dumps(["S2", "S3"])

    await hass.async_block_till_done()
    assert len(mock_config_entry.subentries) == 2
    assert hass.states.get("calendar.second_street_to_third_street") is not None


@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    "feed_zip",
    [
        pytest.param(
            build_feed_zip(
                replace={
                    "stops.txt": (
                        "stop_id,stop_name,stop_lat,stop_lon,"
                        "location_type,parent_station\n"
                        "S1,First Street,40.0,-75.0,,\n"
                        "S2,Second Street,40.01,-75.01,0,\n"
                        "S3,Third Street Platform,40.02,-75.02,0,STA\n"
                        "STA,Third Street Station,40.02,-75.02,1,\n"
                        "ENT,Third Street Entrance,40.02,-75.02,2,STA\n"
                        "N1,Night Depot,40.1,-75.1,,\n"
                        "N2,Night Terminal,40.11,-75.11,,\n"
                    )
                }
            ),
            id="stations",
        )
    ],
)
async def test_add_route_lists_only_stops(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test stations and entrances, which trips never stop at, are not offered."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ROUTE),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_ORIGIN].config["options"]
    assert [option["value"] for option in options] == ["S1", "N1", "N2", "S2", "S3"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _route_input("S2", "S3")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Second Street to Third Street Platform"


@pytest.mark.usefixtures("mock_feed_download")
async def test_add_route_same_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test origin and destination must differ."""
    await setup_integration(hass, mock_config_entry)
    flow_id = await _start_route_flow(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_configure(
        flow_id, _route_input("S1", "S1")
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_stop"}
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_ORIGIN) == "S1"
    assert get_schema_suggested_value(schema, CONF_DESTINATION) == "S1"

    result = await hass.config_entries.subentries.async_configure(
        flow_id, _route_input("S1", "S2")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_feed_download")
async def test_add_route_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a route between the same stops cannot be added twice."""
    await setup_integration(hass, mock_config_entry)
    flow_id = await _start_route_flow(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_configure(
        flow_id, _route_input("S1", "S3")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_add_route_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test routes cannot be added before the feed has loaded."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ROUTE),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def _submit_reconfigure(
    hass: HomeAssistant, flow_id: str, url: str
) -> ConfigFlowResult:
    """Submit url to a reconfigure flow and return the result once it has loaded."""
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_URL: url})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "load_feed"
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


async def _assert_reconfigured(
    hass: HomeAssistant, entry: MockConfigEntry, result: ConfigFlowResult, url: str
) -> None:
    """Assert the entry now uses a new database of the new feed, keeping its routes."""
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    database = entry.data[CONF_DATABASE]
    assert entry.data == {CONF_URL: url, CONF_DATABASE: database}
    assert database != TEST_DATABASE
    assert gtfs_files(hass) == [database]
    assert entry.state is ConfigEntryState.LOADED
    assert "S4" in await hass.async_add_executor_job(list_stops, entry.runtime_data)
    assert list(entry.subentries) == [ROUTE_SUBENTRY_ID]
    assert hass.states.get(ROUTE_ENTITY_ID) is not None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(FEED_URL, id="same_url"),
        pytest.param(NEW_FEED_URL, id="new_url"),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    feed_zip: bytes,
    url: str,
) -> None:
    """Test reconfiguring downloads the feed into a new database and swaps it in."""
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await setup_integration(hass, mock_config_entry)
    assert gtfs_files(hass) == [TEST_DATABASE]

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_URL) == FEED_URL
    )

    aioclient_mock.clear_requests()
    aioclient_mock.get(url, content=NEW_FEED_ZIP)
    result = await _submit_reconfigure(hass, result["flow_id"], url)

    await _assert_reconfigured(hass, mock_config_entry, result, url)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        pytest.param({"exc": ClientError()}, "cannot_connect", id="connection_error"),
        pytest.param({"text": "<html>Not here</html>"}, "invalid_feed", id="html_page"),
        pytest.param(
            {"content": build_feed_zip(exclude=frozenset({"stops.txt"}))},
            "invalid_feed",
            id="missing_stops",
        ),
    ],
)
async def test_reconfigure_load_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    feed_zip: bytes,
    response: dict[str, Any],
    error: str,
) -> None:
    """Test a failed reload keeps the old database in use, then can recover."""
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await setup_integration(hass, mock_config_entry)
    feed = mock_config_entry.runtime_data
    result = await mock_config_entry.start_reconfigure_flow(hass)
    flow_id = result["flow_id"]

    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, **response)
    result = await _submit_reconfigure(hass, flow_id, FEED_URL)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_URL) == FEED_URL
    )
    await hass.async_block_till_done()
    assert gtfs_files(hass) == [TEST_DATABASE]
    assert mock_config_entry.data[CONF_DATABASE] == TEST_DATABASE
    assert mock_config_entry.runtime_data is feed
    assert mock_config_entry.state is ConfigEntryState.LOADED

    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, content=NEW_FEED_ZIP)
    result = await _submit_reconfigure(hass, flow_id, FEED_URL)

    await _assert_reconfigured(hass, mock_config_entry, result, FEED_URL)


async def test_reconfigure_invalid_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    feed_zip: bytes,
) -> None:
    """Test reconfiguring rejects a URL that is not http or https."""
    aioclient_mock.get(FEED_URL, content=feed_zip)
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: "ftp://example.com/gtfs.zip"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_URL: "invalid_url"}

    aioclient_mock.get(NEW_FEED_URL, content=NEW_FEED_ZIP)
    result = await _submit_reconfigure(hass, flow_id, NEW_FEED_URL)

    await _assert_reconfigured(hass, mock_config_entry, result, NEW_FEED_URL)


@pytest.mark.usefixtures("mock_feed_download")
async def test_reconfigure_url_of_other_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring to a URL another entry uses aborts and keeps the feed."""
    await setup_integration(hass, mock_config_entry)
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: OTHER_FEED_URL, CONF_DATABASE: "other.sqlite"},
    ).add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f" {OTHER_FEED_URL} "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_URL] == FEED_URL
    assert gtfs_files(hass) == [TEST_DATABASE]


@pytest.mark.usefixtures("mock_feed_download")
async def test_reconfigure_removed_before_finish(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test abandoning a reconfigure after its import deletes only the new database."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    assert len(gtfs_files(hass)) == 2

    hass.config_entries.flow.async_abort(flow_id)
    # Flow removal deletes the database in a background executor job.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert gtfs_files(hass) == [TEST_DATABASE]
    assert mock_config_entry.data[CONF_DATABASE] == TEST_DATABASE
    assert mock_config_entry.state is ConfigEntryState.LOADED
