"""Fixtures for the tests for the feedreader component."""

import pytest

from homeassistant.components.feedreader.coordinator import EVENT_FEEDREADER
from homeassistant.core import Event, HomeAssistant

from . import load_fixture_bytes

from tests.common import async_capture_events


@pytest.fixture(name="feed_one_event")
def fixture_feed_one_event(hass: HomeAssistant) -> bytes:
    """Load test feed data for one event."""
    return load_fixture_bytes("feedreader.xml")


@pytest.fixture(name="feed_two_event")
def fixture_feed_two_events(hass: HomeAssistant) -> bytes:
    """Load test feed data for two event."""
    return load_fixture_bytes("feedreader1.xml")


@pytest.fixture(name="feed_21_events")
def fixture_feed_21_events(hass: HomeAssistant) -> bytes:
    """Load test feed data for twenty one events."""
    return load_fixture_bytes("feedreader2.xml")


@pytest.fixture(name="feed_three_events")
def fixture_feed_three_events(hass: HomeAssistant) -> bytes:
    """Load test feed data for three events."""
    return load_fixture_bytes("feedreader3.xml")


@pytest.fixture(name="feed_four_events")
def fixture_feed_four_events(hass: HomeAssistant) -> bytes:
    """Load test feed data for three events."""
    return load_fixture_bytes("feedreader4.xml")


@pytest.fixture(name="feed_atom_event")
def fixture_feed_atom_event(hass: HomeAssistant) -> bytes:
    """Load test feed data for atom event."""
    return load_fixture_bytes("feedreader5.xml")


@pytest.fixture(name="feed_identically_timed_events")
def fixture_feed_identically_timed_events(hass: HomeAssistant) -> bytes:
    """Load test feed data for two events published at the exact same time."""
    return load_fixture_bytes("feedreader6.xml")


@pytest.fixture(name="feed_without_items")
def fixture_feed_without_items(hass: HomeAssistant) -> bytes:
    """Load test feed without any items."""
    return load_fixture_bytes("feedreader7.xml")


@pytest.fixture(name="feed_only_summary")
def fixture_feed_only_summary(hass: HomeAssistant) -> bytes:
    """Load test feed data with one event containing only a summary, no content."""
    return load_fixture_bytes("feedreader8.xml")


@pytest.fixture(name="feed_htmlentities")
def fixture_feed_htmlentities(hass: HomeAssistant) -> bytes:
    """Load test feed data with HTML Entities."""
    return load_fixture_bytes("feedreader9.xml")


@pytest.fixture(name="feed_atom_htmlentities")
def fixture_feed_atom_htmlentities(hass: HomeAssistant) -> bytes:
    """Load test ATOM feed data with HTML Entities."""
    return load_fixture_bytes("feedreader10.xml")


@pytest.fixture(name="events")
async def fixture_events(hass: HomeAssistant) -> list[Event]:
    """Fixture that catches alexa events."""
    return async_capture_events(hass, EVENT_FEEDREADER)
