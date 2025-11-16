"""Tests for the AdGuard Home integration."""

from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    aioclient_mock.get(
        "https://127.0.0.1:3000/control/status",
        json={"version": "v0.107.50"},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
