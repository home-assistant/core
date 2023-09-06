"""Test the Aurora ABB PowerOne Solar PV config flow."""
from logging import INFO
from unittest.mock import patch

from aurorapy.client import AuroraError, AuroraTimeoutError
from serial.tools import list_ports_common

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

TEST_DATA = {"device": "/dev/ttyUSB7", "address": 3, "name": "MyAuroraPV"}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    fakecomports = []
    fakecomports.append(list_ports_common.ListPortInfo("/dev/ttyUSB7"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        return_value=None,
    ), patch(
        "aurorapy.client.AuroraSerialClient.serial_number",
        return_value="9876543",
    ), patch(
        "aurorapy.client.AuroraSerialClient.version",
        return_value="9.8.7.6",
    ), patch(
        "aurorapy.client.AuroraSerialClient.pn",
        return_value="A.B.C",
    ), patch(
        "aurorapy.client.AuroraSerialClient.firmware",
        return_value="1.234",
    ), patch(
        "homeassistant.components.aurora_abb_powerone.config_flow._LOGGER.getEffectiveLevel",
        return_value=INFO,
    ) as mock_setup, patch(
        "homeassistant.components.aurora_abb_powerone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

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


async def test_form_no_comports(hass: HomeAssistant) -> None:
    """Test we display correct info when there are no com ports.."""

    fakecomports = []
    with patch(
        "serial.tools.list_ports.comports",
        return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "abort"
    assert result["reason"] == "no_serial_ports"


async def test_form_invalid_com_ports(hass: HomeAssistant) -> None:
    """Test we display correct info when the comport is invalid.."""

    fakecomports = []
    fakecomports.append(list_ports_common.ListPortInfo("/dev/ttyUSB7"))
    with patch(
        "serial.tools.list_ports.comports",
        return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=OSError(19, "...no such device..."),
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "invalid_serial_port"}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError("..could not open port..."),
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "cannot_open_serial_port"}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraTimeoutError("...No response after..."),
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError("...Some other message!!!123..."),
        return_value=None,
    ), patch(
        "serial.Serial.isOpen",
        return_value=True,
    ), patch(
        "aurorapy.client.AuroraSerialClient.close",
    ) as mock_clientclose:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_clientclose.mock_calls) == 1
