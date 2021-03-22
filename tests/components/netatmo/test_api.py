"""The tests for the Netatmo oauth2 api."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.setup import async_setup_component


async def test_api(hass, config_entry):
    """Test auth instantiation."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch("homeassistant.components.webhook.async_generate_url"):
        assert await async_setup_component(hass, "netatmo", {})

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED
