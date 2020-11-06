"""Test the Aurora ABB PowerOne Solar PV config flow."""
from aurorapy.client import AuroraError, AuroraSerialClient
from serial.tools import list_ports_common

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.aurora_abb_powerone.aurora_device import AuroraDevice
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    CONF_USEDUMMYONFAIL,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from tests.async_mock import patch


async def test_create_auroradevice(hass):
    """Test creation of an aurora abb powerone device."""
    client = AuroraSerialClient(7, "/dev/ttyUSB7", parity="N", timeout=1)
    config = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            ATTR_SERIAL_NUMBER: "65432",
            ATTR_MODEL: "AAYYBB",
            ATTR_DEVICE_NAME: "Feathers McGraw",
            ATTR_FIRMWARE: "0.1.2.3",
        },
        source="dummysource",
        connection_class=CONN_CLASS_LOCAL_POLL,
        system_options={},
        entry_id="13579",
    )
    device = AuroraDevice(client, config)
    uid = device.unique_id
    assert uid == "65432_device"

    available = device.available
    assert available

    info = device.device_info
    assert info == {
        "config_entry_id": "13579",
        "identifiers": {(DOMAIN, "65432")},
        "manufacturer": MANUFACTURER,
        "model": "AAYYBB",
        "name": "Feathers McGraw",
        "sw_version": "0.1.2.3",
    }


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    fakecomports = []
    fakecomports.append(list_ports_common.ListPortInfo("/dev/ttyUSB7"))
    for p in fakecomports:
        print("fake port = %s" % p)
    with patch(
        "serial.tools.list_ports.comports",
        return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None,), patch(
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
        "homeassistant.components.aurora_abb_powerone.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.aurora_abb_powerone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
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


async def test_form_no_comports(hass):
    """Test we display correct info when there are no com ports.."""

    fakecomports = []
    with patch(
        "serial.tools.list_ports.comports",
        return_value=fakecomports,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    print("result=%s" % result)
    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_serial_ports"}


async def test_form_invalid_com_ports(hass):
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
    print("result=%s" % result)
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=OSError("...no such device..."),
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
        side_effect=AuroraError("...No response after..."),
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_populate_defaults(hass):
    """Test we populate with defaults if the user ticks that option."""

    fakecomports = []
    fakecomports.append(list_ports_common.ListPortInfo("/dev/ttyUSB7"))

    with patch("serial.tools.list_ports.comports", return_value=fakecomports,), patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.DEBUGMODE",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    print("result=%s" % result)
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError,
        return_value=None,
    ), patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.DEBUGMODE",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7, CONF_USEDUMMYONFAIL: True},
        )
    print("result2=%s" % result2)
    assert result2["data"] == {
        "title": DEFAULT_INTEGRATION_TITLE,
        "serial_number": "735492",
        "pn": "-3G97-",
        "firmware": "C.0.3.5",
        CONF_ADDRESS: 7,
        CONF_PORT: "/dev/ttyUSB7",
        CONF_USEDUMMYONFAIL: True,
    }
