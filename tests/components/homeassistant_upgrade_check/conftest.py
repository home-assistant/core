"""Fixtures for the Home Assistant Upgrade Check tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.homeassistant_upgrade_check.const import DOMAIN
from homeassistant.components.homeassistant_upgrade_check.feed import (
    POST_URL,
    POSTS_URL,
)
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

POSTS = Path(__file__).parent / "fixtures" / "posts"
MOCK_CORE_UPDATE = "update.home_assistant_core_mock"
# The upgrade the fixture posts are written around, independent of the mock's.
RUNNING = "2026.7.0"
TARGET = "2026.11.0"


@pytest.fixture(autouse=True)
def mock_release_notes(aioclient_mock: AiohttpClientMocker) -> Generator[None]:
    """Serve the fixture release posts as the home-assistant.io repository."""
    posts = sorted(POSTS.iterdir())
    aioclient_mock.get(
        POSTS_URL,
        json={
            "tree": [
                {"path": "2026-11-05-not-a-release.markdown"},
                *({"path": post.name} for post in posts),
            ]
        },
    )
    for post in posts:
        aioclient_mock.get(POST_URL.format(name=post.name), text=post.read_text())
    # Only what a test sets up counts as installed.
    with patch(
        "homeassistant.components.homeassistant_upgrade_check.websocket_api.MOCK_DOMAINS",
        frozenset(),
    ):
        yield


@pytest.fixture
def installed_integrations(hass: HomeAssistant) -> None:
    """Add config entries for the integrations this installation uses."""
    for domain in ("mqtt", "hue", "gardena_bluetooth", "old_thing"):
        MockConfigEntry(domain=domain).add_to_hass(hass)
    # A dismissed discovery is not an installed integration.
    MockConfigEntry(domain="zha", source=SOURCE_IGNORE).add_to_hass(hass)
    # Entity types and system parts are loaded on every installation. An entity
    # type only counts once there are such entities; system parts are general.
    for domain in ("calendar", "vacuum", "auth"):
        hass.config.components.add(domain)
    hass.states.async_set("calendar.home", "off")


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the upgrade check with a core update from RUNNING to TARGET."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    hass.states.async_set(
        MOCK_CORE_UPDATE,
        STATE_ON,
        {ATTR_INSTALLED_VERSION: RUNNING, ATTR_LATEST_VERSION: TARGET},
    )
