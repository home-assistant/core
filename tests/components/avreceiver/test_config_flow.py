"""Tests for the AV Receiver config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.avreceiver.config_flow import AVReceiverFlowHandler


async def test_flow_aborts_already_setup(hass, config_entry):
    """Test flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)
    flow = AVReceiverFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_no_host_shows_form(hass):
    """Test form is shown when host not provided."""
    flow = AVReceiverFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


# async def test_cannot_connect_shows_error_form(hass, avr):
#     """Test form is shown with error when cannot connect."""
#     avr.init.side_effect = AVReceiverIncompatibleDeviceError()
#     result = await hass.config_entries.flow.async_init(
#         avreceiver.DOMAIN, context={"source": "user"}, data={CONF_HOST: "127.0.0.1"}
#     )
#     assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
#     assert result["step_id"] == "user"
#     assert result["errors"][CONF_HOST] == "cannot_connect"
#     # assert controller.connect.call_count == 1
#     # assert controller.disconnect.call_count == 1
#     # controller.connect.reset_mock()
#     # controller.disconnect.reset_mock()
