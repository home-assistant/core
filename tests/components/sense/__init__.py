"""Tests for the Sense integration."""

from unittest.mock import patch

from homeassistant.components.sense.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, platform: str | None = None
) -> MockConfigEntry:
    """Set up the Sense platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test-email",
    )
    mock_entry.add_to_hass(hass)

    if platform:
        with patch("homeassistant.components.sense.PLATFORMS", [platform]):
            assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry
