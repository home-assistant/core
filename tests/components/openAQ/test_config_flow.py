"""Test the OpenAQ config flow."""


# async def test_api_key_incorrect(hass: HomeAssistant, mock_aq_client_for_config_flow):
#     """Test if user input for API key is incorrect."""
#     # Mocking the AQClient with predefined responses for config flow
#     mock_aq_client_for_config_flow(hass)
#     await hass.async_block_till_done()

#     # Starting the flow
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     # Simulating user input with no  API key but a location id
#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         {
#             "api_id": " ",
#             "location_id": "test_location",
#         },
#     )

#     # Check the result
#     assert result["type"] == data_entry_flow.FlowResultType.FORM
#     assert result["step_id"] == "test_location"
