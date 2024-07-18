"""Test the DoorBird config flow."""

from unittest.mock import MagicMock

from homeassistant.components.doorbird.const import CONF_EVENTS, DOMAIN
from homeassistant.core import HomeAssistant

from . import VALID_CONFIG

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, doorbird_api: MagicMock) -> None:
    """Test the setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1CCAE3AAAAAA",
        data=VALID_CONFIG,
        options={CONF_EVENTS: ["event1", "event2", "event3"]},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
