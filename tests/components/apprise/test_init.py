"""The tests for the Apprise component."""

from homeassistant.components import apprise
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configuration."""
    entry = MockConfigEntry(
        domain=apprise.DOMAIN,
        data={"host1": "host1"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
