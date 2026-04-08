"""Common fixtures for SpaceAPI tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "spaceapi"

ENTRY_DATA = {
    "space": "Home",
    "logo": "https://home-assistant.io/logo.png",
    "url": "https://home-assistant.io",
    "state": {"entity_id": "test.test_door"},
    "contact": {"email": "hello@home-assistant.io"},
    "issue_report_channels": ["email"],
}

ENTRY_OPTIONS = {
    "contact": {"email": "hello@home-assistant.io"},
    "state": {
        "icon_open": "https://home-assistant.io/open.png",
        "icon_closed": "https://home-assistant.io/close.png",
    },
    "sensors": {
        "temperature": ["test.temp1", "test.temp2", "test.temp3"],
        "humidity": ["test.hum1"],
    },
    "spacefed": {"spacenet": True, "spacesaml": False, "spacephone": True},
    "cam": ["https://home-assistant.io/cam1", "https://home-assistant.io/cam2"],
    "stream": {
        "m4": "https://home-assistant.io/m4",
        "mjpeg": "https://home-assistant.io/mjpeg",
        "ustream": "https://home-assistant.io/ustream",
    },
    "feeds": {
        "blog": {"url": "https://home-assistant.io/blog"},
        "wiki": {"type": "mediawiki", "url": "https://home-assistant.io/wiki"},
        "calendar": {"type": "ical", "url": "https://home-assistant.io/calendar"},
        "flicker": {"url": "https://www.flickr.com/photos/home-assistant"},
    },
    "cache": {"schedule": "m.02"},
    "projects": [
        "https://home-assistant.io/projects/1",
        "https://home-assistant.io/projects/2",
        "https://home-assistant.io/projects/3",
    ],
    "radio_show": [
        {
            "name": "Radioshow",
            "url": "https://home-assistant.io/radio",
            "type": "ogg",
            "start": "2019-09-02T10:00Z",
            "end": "2019-09-02T12:00Z",
        }
    ],
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.spaceapi.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a SpaceAPI mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)
    return entry
