"""Tests for the LinkPlay option flow."""


from tests.common import MockConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.linkplay.config_flow import LinkPlayOptionsFlow
from homeassistant.components.linkplay.const import DOMAIN

import pytest

@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Mock a ConfigEntry for LinkPlay Options."""
    entry = MockConfigEntry(
        domain=DOMAIN,  
        title="Test Entry",
        data={"use_ip_url": True},
        options={"use_ip_url": False},
    )
    entry.add_to_hass(hass)
    return entry

async def test_options_flow(hass: HomeAssistant, mock_config_entry):
    """Test the options flow for the LinkPlay component."""

    # Initialize the options flow
    flow = LinkPlayOptionsFlow()

    # Start the options flow
    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await flow.async_step_update_options(user_input={"use_ip_url": True})

    # Ensure that the new options are processed correctly
    assert result["type"] == "create_entry"
    assert mock_config_entry.options == {"use_ip_url": True}
