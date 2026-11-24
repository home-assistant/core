"""Tests for the google_wifi component."""

from typing import Any

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant

from .const import build_response, status_url


def mock_device(
    aioclient_mock: AiohttpClientMocker,
    host: str,
    response: dict[str, Any] | None = None,
) -> None:
    """Mock a Google Wifi device at a host."""
    aioclient_mock.get(
        status_url(host),
        json=response if response is not None else build_response(),
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add a config entry and set it up."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
