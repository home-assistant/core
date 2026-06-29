"""Tests for Google Health integration lifecycle (init/unloading)."""

from collections.abc import Awaitable, Callable

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .conftest import ROLLUP_URL, SETTINGS_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard setup and unloading of the config entry."""
    aioclient_mock.get(
        SETTINGS_URL,
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        ROLLUP_URL,
        json={
            "rollupDataPoints": [
                {
                    "steps": {
                        "countSum": 10500,
                    },
                    "civilStartTime": {"date": {"year": 2026, "month": 6, "day": 28}},
                    "civilEndTime": {"date": {"year": 2026, "month": 6, "day": 29}},
                }
            ]
        },
    )

    # Setup the integration
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    # Unload integration
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_setup_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error retry handling when API fails."""
    aioclient_mock.get(
        SETTINGS_URL,
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        ROLLUP_URL,
        status=500,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error when API returns auth or forbidden errors."""
    aioclient_mock.get(
        SETTINGS_URL,
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        ROLLUP_URL,
        status=403,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR
