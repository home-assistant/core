"""The tests for the feedreader event entity."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.feedreader.event import (
    ATTR_CONTENT,
    ATTR_DESCRIPTION,
    ATTR_LINK,
    ATTR_TITLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import create_mock_entry
from .const import VALID_CONFIG_DEFAULT

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("fixture_name", "expected_attributes"),
    [
        (
            "feed_one_event",
            {
                ATTR_TITLE: "Title 1",
                ATTR_LINK: "http://www.example.com/link/1",
                ATTR_CONTENT: "Content 1",
                ATTR_DESCRIPTION: "Description 1",
            },
        ),
        (
            "feed_two_event",
            {
                ATTR_TITLE: "Title 2",
                ATTR_LINK: "http://www.example.com/link/2",
                ATTR_CONTENT: "Content 2",
                ATTR_DESCRIPTION: "Description 2",
            },
        ),
        (
            "feed_only_summary",
            {
                ATTR_TITLE: "Title 1",
                ATTR_LINK: "http://www.example.com/link/1",
                ATTR_CONTENT: "This is a summary",
                ATTR_DESCRIPTION: "Description 1",
            },
        ),
    ],
)
async def test_event_entity(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    fixture_name: str,
    expected_attributes: dict[str, str],
) -> None:
    """Test feed event entity."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[request.getfixturevalue(fixture_name)],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        for attribute, value in expected_attributes.items():
            assert state.attributes[attribute] == value


async def test_event_new_entry_sorted(
    hass: HomeAssistant, feed_one_event: bytes, feed_two_event: bytes
) -> None:
    """Test feed event entity fires on new event."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[feed_one_event, feed_two_event],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 1"
        assert state.attributes[ATTR_LINK] == "http://www.example.com/link/1"
        assert state.attributes[ATTR_CONTENT] == "Content 1"
        assert state.attributes[ATTR_DESCRIPTION] == "Description 1"

        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)
        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 2"
        assert state.attributes[ATTR_LINK] == "http://www.example.com/link/2"
        assert state.attributes[ATTR_CONTENT] == "Content 2"
        assert state.attributes[ATTR_DESCRIPTION] == "Description 2"


async def test_event_new_entry_unsorted(
    hass: HomeAssistant, feed_unsorted: bytes, feed_unsorted_update: bytes
) -> None:
    """Test feed event entity fires on new event."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[feed_unsorted, feed_unsorted_update],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 3"
        assert state.attributes[ATTR_CONTENT] == "Content 3"

        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)
        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 4"
        assert state.attributes[ATTR_CONTENT] == "Content 4"


@pytest.mark.parametrize(
    ("fixture_name"),
    [
        ("feed_htmlentities"),
        ("feed_atom_htmlentities"),
    ],
)
async def test_event_htmlentities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    fixture_name: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test feed event entity with HTML Entities."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[request.getfixturevalue(fixture_name)],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes == snapshot


async def test_event_no_new_entry(hass: HomeAssistant, feed_two_event: bytes) -> None:
    """Test feed event entity is not firing when there are no new entries."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[feed_two_event, feed_two_event],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        old_state = state

        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)
        state = hass.states.get("event.mock_title")
        assert state == old_state
