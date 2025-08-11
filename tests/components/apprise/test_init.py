"""The tests for the Apprise component."""

from unittest.mock import patch

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

    with patch(
        "homeassistant.components.apprise.validate_apprise_connection",
        return_value=False,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
