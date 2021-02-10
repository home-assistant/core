"""The tests for the Netatmo climate platform."""
from unittest.mock import patch

from homeassistant.components.netatmo import api


async def test_api(hass, config_entry):
    """Test api."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as fake_implementation:
        auth = api.ConfigEntryNetatmoAuth(hass, config_entry, fake_implementation)

    assert isinstance(auth, api.ConfigEntryNetatmoAuth)
