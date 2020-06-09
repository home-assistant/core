"""Test the Aurora ABB PowerOne Solar PV config flow."""
# from aurorapy.client import AuroraError, AuroraSerialClient

from serial.tools import list_ports_common

# from homeassistant.components.aurora_abb_powerone.config_flow import (
#     CannotConnect,
#     InvalidAuth,
# )
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    fakecomports = []
    fakecomports.append(list_ports_common.ListPortInfo("/dev/ttyUSB7"))
    for p in fakecomports:
        print("fake port = %s" % p)
    with patch(
        "serial.tools.list_ports.comports", return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("serial.tools.list_ports.comports", return_value=fakecomports,), patch(
        "aurorapy.client.AuroraSerialClient.connect", return_value=None,
    ), patch(
        "aurorapy.client.AuroraSerialClient.serial_number", return_value="9876543",
    ), patch(
        "aurorapy.client.AuroraSerialClient.version", return_value="9.8.7.6",
    ), patch(
        "aurorapy.client.AuroraSerialClient.pn", return_value="A.B.C",
    ), patch(
        "aurorapy.client.AuroraSerialClient.firmware", return_value="1.234",
    ), patch(
        "homeassistant.components.aurora_abb_powerone.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.aurora_abb_powerone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert result2["data"] == {
        CONF_PORT: "/dev/ttyUSB7",
        CONF_ADDRESS: 7,
        ATTR_FIRMWARE: "1.234",
        ATTR_MODEL: "9.8.7.6 (A.B.C)",
        ATTR_SERIAL_NUMBER: "9876543",
        "title": "PhotoVoltaic Inverters",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


# async def test_form_invalid_auth(hass):
#     """Test we handle invalid auth."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     with patch(
#         "homeassistant.components.aurora_abb_powerone.config_flow.PlaceholderHub.authenticate",
#         side_effect=InvalidAuth,
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )

#     assert result2["type"] == "form"
#     assert result2["errors"] == {"base": "invalid_auth"}


# async def test_form_cannot_connect(hass):
#     """Test we handle cannot connect error."""
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     with patch(
#         "homeassistant.components.aurora_abb_powerone.config_flow.PlaceholderHub.authenticate",
#         side_effect=CannotConnect,
#     ):
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )

#     assert result2["type"] == "form"
#     assert result2["errors"] == {"base": "cannot_connect"}
