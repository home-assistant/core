"""Tests for GTFS config entry setup and removal."""

from pathlib import Path
import threading
from typing import Any
from unittest.mock import patch

from aiohttp import ClientError
import pygtfs
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gtfs.const import (
    CONF_DATABASE,
    DEFAULT_PATH,
    DOMAIN,
    FLOW_DATABASES,
)
from homeassistant.components.gtfs.feed import (
    close_feed,
    feed_database_path,
    remove_files,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

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


ORPHAN = "a" * 32
OTHER_ORPHAN = "b" * 32
KEPT = "c" * 32
ORPHAN_FILES = [
    f"{ORPHAN}.zip",
    f"{ORPHAN}.sqlite.tmp",
    f"{OTHER_ORPHAN}.sqlite",
]
UNRELATED_FILES = [
    "abc.sqlite",
    "bart.sqlite",
    "bart.zip",
    "feed.sqlite",
    "feed.zip",
    f"{'D' * 32}.sqlite",
    f"{KEPT}.sqlite.bak",
    f"x{KEPT}.zip",
]


def _create_files(hass: HomeAssistant, names: list[str]) -> None:
    directory = Path(hass.config.path(DEFAULT_PATH))
    directory.mkdir(exist_ok=True)
    for name in names:
        (directory / name).touch()


async def test_setup_removes_orphaned_feed_files(hass: HomeAssistant) -> None:
    """Test files no entry or flow owns are removed and everything else is kept."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: FEED_URL, CONF_DATABASE: f"{KEPT}.sqlite"},
    ).add_to_hass(hass)
    kept = [f"{KEPT}.sqlite", *UNRELATED_FILES]
    _create_files(hass, [*ORPHAN_FILES, *kept])

    with patch("homeassistant.components.gtfs.async_setup_entry", return_value=None):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert gtfs_files(hass) == sorted(kept)


async def test_setup_keeps_database_of_disabled_entry(hass: HomeAssistant) -> None:
    """Test a database owned by a disabled entry is kept."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: FEED_URL, CONF_DATABASE: f"{KEPT}.sqlite"},
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    _create_files(hass, [f"{KEPT}.sqlite", *ORPHAN_FILES])

    assert await async_setup_component(hass, DOMAIN, {})

    assert gtfs_files(hass) == [f"{KEPT}.sqlite"]


async def test_setup_without_feed_directory(hass: HomeAssistant) -> None:
    """Test setup succeeds when the feed directory does not exist."""
    assert await async_setup_component(hass, DOMAIN, {})

    assert gtfs_files(hass) == []


async def test_setup_survives_listing_failure(hass: HomeAssistant) -> None:
    """Test a directory that cannot be listed leaves its files alone."""
    _create_files(hass, ORPHAN_FILES)

    with patch.object(Path, "iterdir", side_effect=PermissionError):
        assert await async_setup_component(hass, DOMAIN, {})

    assert gtfs_files(hass) == sorted(ORPHAN_FILES)


async def test_flow_databases_released_after_retry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, feed_zip: bytes
) -> None:
    """Test a retried flow tracks only its current database until it finishes."""
    aioclient_mock.get(FEED_URL, exc=ClientError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(hass.data[FLOW_DATABASES]) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(FEED_URL, content=feed_zip)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_URL: FEED_URL}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.data[FLOW_DATABASES] == set()
    assert gtfs_files(hass) == [result["data"][CONF_DATABASE]]


@pytest.mark.usefixtures("mock_feed_download")
async def test_setup_keeps_files_of_flow_in_progress(hass: HomeAssistant) -> None:
    """Test setup keeps the files of a flow importing a feed, then the flow finishes."""
    append_feed = pygtfs.append_feed
    appended = threading.Event()
    release = threading.Event()

    def blocking_append_feed(schedule: pygtfs.Schedule, feed_filename: str) -> None:
        append_feed(schedule, feed_filename)
        appended.set()
        release.wait(10)

    with patch(
        "homeassistant.components.gtfs.feed.pygtfs.append_feed", blocking_append_feed
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_URL: FEED_URL}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert await hass.async_add_executor_job(appended.wait, 10)

        try:
            flow_files = gtfs_files(hass)
            assert [Path(name).suffix for name in flow_files] == [".tmp", ".zip"]
            _create_files(hass, ORPHAN_FILES)

            assert await async_setup_component(hass, DOMAIN, {})

            assert gtfs_files(hass) == flow_files
        finally:
            release.set()

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.data[FLOW_DATABASES] == set()
    assert gtfs_files(hass) == [result["data"][CONF_DATABASE]]


def test_remove_files_skips_files_it_cannot_remove(tmp_path: Path) -> None:
    """Test a name that cannot be unlinked is skipped without raising."""
    directory = tmp_path / "gtfs"
    directory.mkdir()
    (directory / f"{ORPHAN}.zip").mkdir()
    (directory / f"{OTHER_ORPHAN}.zip").touch()

    assert remove_files(sorted(directory.iterdir())) == 1

    assert [path.name for path in directory.iterdir()] == [f"{ORPHAN}.zip"]
