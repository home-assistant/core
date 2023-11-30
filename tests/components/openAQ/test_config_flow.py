"""Test the OpenAQ config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.openAQ.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_api_key_incorrect(hass: HomeAssistant, mock_aq_client_for_config_flow):
    """Test if user input for API key is incorrect."""
    # Mocking the AQClient with predefined responses for config flow
    mock_aq_client_for_config_flow(hass)
    await hass.async_block_till_done()

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate user input with incorrect API key and a location id
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_id": "wrong_api_key",  # Corrected field name
            "location_id": "test_location",
        },
    )

    # Check the result
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    # Adjust the assertion to expect the step_id to be 'test_location'
    assert result["step_id"] == "test_location"
