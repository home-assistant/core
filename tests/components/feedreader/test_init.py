"""The tests for the feedreader component."""

from datetime import datetime, timedelta
from time import gmtime
from typing import Any
from unittest.mock import patch
import urllib
import urllib.error

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.feedreader.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import async_setup_config_entry, create_mock_entry
from .const import (
    URL,
    VALID_CONFIG_1,
    VALID_CONFIG_5,
    VALID_CONFIG_100,
    VALID_CONFIG_DEFAULT,
)

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    "config",
    [VALID_CONFIG_DEFAULT, VALID_CONFIG_1, VALID_CONFIG_100, VALID_CONFIG_5],
)
async def test_setup(
    hass: HomeAssistant,
    events: list[Event],
    feed_one_event: bytes,
    hass_storage: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """Test loading existing storage data."""
    storage_data: dict[str, str] = {URL: "2018-04-30T05:10:00+00:00"}
    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": DOMAIN,
        "data": storage_data,
    }
    assert await async_setup_config_entry(hass, config, return_value=feed_one_event)

    # no new events
    assert not events


async def test_setup_error(
    hass: HomeAssistant,
    feed_one_event,
) -> None:
    """Test setup error."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get"
    ) as feedreader:
        feedreader.side_effect = urllib.error.URLError("Test")
        feedreader.return_value = feed_one_event
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_storage_data_writing(
    hass: HomeAssistant,
    events: list[Event],
    feed_one_event: bytes,
    hass_storage: dict[str, Any],
) -> None:
    """Test writing to storage."""
    storage_data: dict[str, str] = {URL: "2018-04-30T05:10:00+00:00"}

    with (
        patch("homeassistant.components.feedreader.coordinator.DELAY_SAVE", new=0),
    ):
        assert await async_setup_config_entry(
            hass, VALID_CONFIG_DEFAULT, return_value=feed_one_event
        )

    # one new event
    assert len(events) == 1

    # storage data updated
    assert hass_storage[DOMAIN]["data"] == storage_data


async def test_feed(hass: HomeAssistant, events, feed_one_event) -> None:
    """Test simple rss feed with valid data."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_one_event
    )

    assert len(events) == 1
    assert events[0].data.title == "Title 1"
    assert events[0].data.description == "Description 1"
    assert events[0].data.link == "http://www.example.com/link/1"
    assert events[0].data.id == "GUID 1"
    assert events[0].data.published_parsed.tm_year == 2018
    assert events[0].data.published_parsed.tm_mon == 4
    assert events[0].data.published_parsed.tm_mday == 30
    assert events[0].data.published_parsed.tm_hour == 5
    assert events[0].data.published_parsed.tm_min == 10


async def test_atom_feed(hass: HomeAssistant, events, feed_atom_event) -> None:
    """Test simple atom feed with valid data."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_atom_event
    )

    assert len(events) == 1
    assert events[0].data.title == "Atom-Powered Robots Run Amok"
    assert events[0].data.description == "Some text."
    assert events[0].data.link == "http://example.org/2003/12/13/atom03"
    assert events[0].data.id == "urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a"
    assert events[0].data.updated_parsed.tm_year == 2003
    assert events[0].data.updated_parsed.tm_mon == 12
    assert events[0].data.updated_parsed.tm_mday == 13
    assert events[0].data.updated_parsed.tm_hour == 18
    assert events[0].data.updated_parsed.tm_min == 30


async def test_feed_identical_timestamps(
    hass: HomeAssistant, events, feed_identically_timed_events
) -> None:
    """Test feed with 2 entries with identical timestamps."""
    with (
        patch(
            "homeassistant.components.feedreader.coordinator.StoredData.get_timestamp",
            return_value=gmtime(
                datetime.fromisoformat("1970-01-01T00:00:00.0+0000").timestamp()
            ),
        ),
    ):
        assert await async_setup_config_entry(
            hass, VALID_CONFIG_DEFAULT, return_value=feed_identically_timed_events
        )

    assert len(events) == 2
    assert events[0].data.title == "Title 1"
    assert events[1].data.title == "Title 2"
    assert events[0].data.link == "http://www.example.com/link/1"
    assert events[1].data.link == "http://www.example.com/link/2"
    assert events[0].data.id == "GUID 1"
    assert events[1].data.id == "GUID 2"
    assert (
        events[0].data.updated_parsed.tm_year
        == events[1].data.updated_parsed.tm_year
        == 2018
    )
    assert (
        events[0].data.updated_parsed.tm_mon
        == events[1].data.updated_parsed.tm_mon
        == 4
    )
    assert (
        events[0].data.updated_parsed.tm_mday
        == events[1].data.updated_parsed.tm_mday
        == 30
    )
    assert (
        events[0].data.updated_parsed.tm_hour
        == events[1].data.updated_parsed.tm_hour
        == 15
    )
    assert (
        events[0].data.updated_parsed.tm_min
        == events[1].data.updated_parsed.tm_min
        == 10
    )
    assert (
        events[0].data.updated_parsed.tm_sec
        == events[1].data.updated_parsed.tm_sec
        == 0
    )


async def test_feed_with_only_summary(
    hass: HomeAssistant, events, feed_only_summary
) -> None:
    """Test simple feed with only summary, no content."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_only_summary
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data.title == "Title 1"
    assert events[0].data.description == "Description 1"
    assert events[0].data.content[0].value == "This is a summary"


async def test_feed_updates(
    hass: HomeAssistant, events, feed_one_event, feed_two_event
) -> None:
    """Test feed updates."""
    side_effect = [
        feed_one_event,
        feed_two_event,
        feed_two_event,
    ]

    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=side_effect,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(events) == 1

        # Change time and fetch more entries
        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(events) == 2

        # Change time but no new entries
        future = dt_util.utcnow() + timedelta(hours=2, seconds=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert len(events) == 2


async def test_feed_default_max_length(
    hass: HomeAssistant, events, feed_21_events
) -> None:
    """Test long feed beyond the default 20 entry limit."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_21_events
    )
    await hass.async_block_till_done()

    assert len(events) == 20


async def test_feed_max_length(hass: HomeAssistant, events, feed_21_events) -> None:
    """Test long feed beyond a configured 5 entry limit."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_5, return_value=feed_21_events
    )
    await hass.async_block_till_done()

    assert len(events) == 5


async def test_feed_without_publication_date_and_title(
    hass: HomeAssistant, events, feed_three_events
) -> None:
    """Test simple feed with entry without publication date and title."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_three_events
    )
    await hass.async_block_till_done()

    assert len(events) == 3


async def test_feed_with_unrecognized_publication_date(
    hass: HomeAssistant, events, feed_four_events
) -> None:
    """Test simple feed with entry with unrecognized publication date."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_four_events
    )
    await hass.async_block_till_done()

    assert len(events) == 1


async def test_feed_without_items(
    hass: HomeAssistant, events, feed_without_items, caplog: pytest.LogCaptureFixture
) -> None:
    """Test simple feed without any items."""
    assert "No new entries to be published in feed" not in caplog.text
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=feed_without_items
    )
    await hass.async_block_till_done()

    assert "No new entries to be published in feed" in caplog.text
    assert len(events) == 0


async def test_feed_invalid_data(hass: HomeAssistant, events) -> None:
    """Test feed with invalid data."""
    assert await async_setup_config_entry(
        hass, VALID_CONFIG_DEFAULT, return_value=bytes("INVALID DATA", "utf-8")
    )
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_feed_parsing_failed(
    hass: HomeAssistant, events, feed_one_event, caplog: pytest.LogCaptureFixture
) -> None:
    """Test feed where parsing fails."""
    assert "Error fetching feed data" not in caplog.text

    with patch("feedparser.parse", return_value=None):
        assert not await async_setup_config_entry(
            hass, VALID_CONFIG_DEFAULT, return_value=feed_one_event
        )
        await hass.async_block_till_done()

    assert "Error fetching feed data" in caplog.text
    assert not events


async def test_feed_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    feed_one_event,
) -> None:
    """Test feed errors."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get"
    ) as feedreader:
        # success setup
        feedreader.return_value = feed_one_event
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # raise URL error
        feedreader.side_effect = urllib.error.URLError("Test")
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert (
            "Error fetching feed data from http://some.rss.local/rss_feed.xml : <urlopen error Test>"
            in caplog.text
        )

        # success
        feedreader.side_effect = None
        feedreader.return_value = feed_one_event
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        caplog.clear()

        # no feed returned
        freezer.tick(timedelta(hours=1, seconds=1))
        with patch(
            "homeassistant.components.feedreader.coordinator.feedparser.parse",
            return_value=None,
        ):
            async_fire_time_changed(hass)
            await hass.async_block_till_done(wait_background_tasks=True)
            assert (
                "Error fetching feed data from http://some.rss.local/rss_feed.xml"
                in caplog.text
            )
            caplog.clear()

        # success
        feedreader.side_effect = None
        feedreader.return_value = feed_one_event
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


async def test_feed_atom_htmlentities(
    hass: HomeAssistant, feed_atom_htmlentities, device_registry: dr.DeviceRegistry
) -> None:
    """Test ATOM feed author with HTML Entities."""

    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[feed_atom_htmlentities],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        assert device_entry.manufacturer == "Juan Pérez"
