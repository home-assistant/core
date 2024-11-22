"""Test the Imeon Inverter config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.imeon_inverter import config_flow
from homeassistant.components.imeon_inverter.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Sample test data
TEST_USER_INPUT = {
    "inverter": "Imeon",
    CONF_ADDRESS: "192.168.200.86",
    CONF_USERNAME: "user@local",
    CONF_PASSWORD: "password",
}


@pytest.fixture
def get_config_flow():
    """Create an instance of the config flow for testing."""
    return config_flow.ImeonInverterConfigFlow()


async def test_show_form_initial_step(get_config_flow) -> None:
    """Test that the initial step shows the configuration form."""
    result = await get_config_flow.async_step_user(user_input=None)

    # Verify that a form is returned
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "data_schema" in result


async def test_create_entry(get_config_flow, hass: HomeAssistant) -> None:
    """Test that a valid user input creates a configuration entry."""
    # Mock the async_create_entry method to simulate Home Assistant behavior
    mock_create_entry = MagicMock()
    get_config_flow.hass = hass
    get_config_flow.async_create_entry = mock_create_entry

    await get_config_flow.async_step_user(user_input=TEST_USER_INPUT)

    # Verify async_create_entry was called with the correct data
    mock_create_entry.assert_called_once_with(
        title=TEST_USER_INPUT["inverter"],
        data={
            "address": TEST_USER_INPUT[CONF_ADDRESS],
            "username": TEST_USER_INPUT[CONF_USERNAME],
            "password": TEST_USER_INPUT[CONF_PASSWORD],
        },
    )


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a flow is aborted if an entry with the same address already exists."""
    # Add an existing entry to Home Assistant
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USER_INPUT["inverter"],
        data={
            "address": TEST_USER_INPUT[CONF_ADDRESS],
            "username": TEST_USER_INPUT[CONF_USERNAME],
            "password": TEST_USER_INPUT[CONF_PASSWORD],
        },
    )
    existing_entry.add_to_hass(hass)

    # Initialize a new flow
    flow = config_flow.ImeonInverterConfigFlow()
    flow.hass = hass

    # Run the user step
    result = await flow.async_step_user(user_input=TEST_USER_INPUT)

    # Verify the flow aborts
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
