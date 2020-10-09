"""Tests for the srp_energy sensor platform."""
# from homeassistant.bootstrap import async_setup_component
# from homeassistant.components import srp_energy
# from homeassistant.const import CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

# from tests.async_mock import patch

# async def test_setup_entry(hass):
#     """Test the default setup."""
#     config = {
#         srp_energy.DOMAIN: {
#             CONF_NAME: "Test",
#             CONF_ID: "1",
#             CONF_USERNAME: "abba",
#             CONF_PASSWORD: "ana",
#         }
#     }
#     mock_form = {
#         CONF_NAME: "Test",
#         CONF_ID: "1",
#         CONF_USERNAME: "abba",
#         CONF_PASSWORD: "ana",
#     }

#     # Setup config first
#     with patch("homeassistant.components.srp_energy.config_flow.SrpEnergyClient"):
#         await hass.config_entries.flow.async_init(
#             srp_energy.DOMAIN, context={"source": "user"}, data=mock_form
#         )

#     await async_setup_component(hass, "sensor", {"sensor": config})
#     await hass.async_block_till_done()

#     state = hass.states.get("sensor.srp_energy")
#     assert state is not None
