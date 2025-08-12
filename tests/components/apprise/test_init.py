"""The tests for the Apprise component."""

from homeassistant.components import apprise
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configuration."""
    entry = MockConfigEntry(
        domain=apprise.DOMAIN,
        data={"config": "http://localhost:8000/get/apprise"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
