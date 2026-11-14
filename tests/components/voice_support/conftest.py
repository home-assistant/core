"""Fixtures for the Voice support tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from aiohasupervisor.models import Discovery
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.voice_support import PREVIEW_FEATURE_NEXT_GENERATION_VOICE
from homeassistant.components.voice_support.app import APP_SLUG
from homeassistant.components.voice_support.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST = "192.168.1.5"
PORT = 10900
APP_HOST = "core-voice"
INFO_URL = f"http://{HOST}:{PORT}/info"
APP_INFO_URL = f"http://{APP_HOST}:{PORT}/info"

INFO = {
    "name": "Voice",
    "version": "1.0.0",
    "api_version": 1,
    "wake_words": [{"id": "okay_nabu", "phrase": "okay nabu"}],
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry, and unloading it."""
    with (
        patch(
            "homeassistant.components.voice_support.async_setup_entry",
            return_value=None,
        ) as mock,
        patch(
            "homeassistant.components.voice_support.async_unload_entry",
            return_value=None,
        ),
    ):
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an entry for an app the person runs."""
    return MockConfigEntry(
        domain=DOMAIN, title="Voice", data={CONF_HOST: HOST, CONF_PORT: PORT}
    )


@pytest.fixture
async def labs(hass: HomeAssistant) -> None:
    """Set up Labs, with the feature off."""
    assert await async_setup_component(hass, "labs", {})


@pytest.fixture
async def preview_feature_enabled(hass: HomeAssistant, labs: None) -> None:
    """Turn on the Labs feature."""
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE, True
    )


@pytest.fixture
def app_info(aioclient_mock: AiohttpClientMocker) -> dict[str, Any]:
    """Make the app answer /info at both addresses it may have."""
    aioclient_mock.get(INFO_URL, json=INFO)
    aioclient_mock.get(APP_INFO_URL, json=INFO)
    return INFO


@pytest.fixture
def supervisor(hass: HomeAssistant) -> None:
    """Run under the Supervisor."""
    hass.config.components.add("hassio")


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> list[Discovery]:
    """Return the app's discovery info."""
    return [
        Discovery(
            addon=APP_SLUG,
            service=DOMAIN,
            uuid=uuid4(),
            config={"host": APP_HOST, "port": PORT},
        )
    ]


@pytest.fixture(autouse=True)
def app_wait_time() -> Generator[None]:
    """Make the app start loop run without delay."""
    with patch(
        "homeassistant.components.voice_support.config_flow.APP_START_INTERVAL", 0
    ):
        yield


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, app_info: dict[str, Any]
) -> MockConfigEntry:
    """Set the entry up against an answering app."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
