"""Common methods used across tests for Epic Games Store."""

from unittest.mock import patch

from homeassistant.components.epic_games_store.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_COUNTRY, MOCK_LANGUAGE

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Epic Games Store platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LANGUAGE: MOCK_LANGUAGE,
            CONF_COUNTRY: MOCK_COUNTRY,
        },
        unique_id=f"freegames-{MOCK_LANGUAGE}-{MOCK_COUNTRY}",
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.epic_games_store.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry
