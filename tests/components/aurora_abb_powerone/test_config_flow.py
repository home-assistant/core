"""Test the Aurora ABB PowerOne Solar PV config flow."""
from datetime import timedelta
from logging import INFO
from unittest.mock import patch

from aurorapy.client import AuroraError
from serial.tools import list_ports_common

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


def _simulated_returns(index, global_measure=None):
    returns = {
        3: 45.678,  # power
        21: 9.876,  # temperature
        5: 12345,  # energy
    }
    return returns[index]


async def test_form(hass):
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
    assert result["type"] == "abort"
    assert result["reason"] == "no_serial_ports"


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
    ), patch("serial.Serial.isOpen", return_value=True,), patch(
        "aurorapy.client.AuroraSerialClient.close",
    ) as mock_clientclose:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_clientclose.mock_calls) == 1


# Tests below can be deleted after deprecation period is finished.
async def test_import_day(hass):
    """Test .yaml import when the inverter is able to communicate."""
    TEST_DATA = {"device": "/dev/ttyUSB7", "address": 3, "name": "MyAuroraPV"}

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
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_PORT] == "/dev/ttyUSB7"
    assert result["data"][CONF_ADDRESS] == 3
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_night(hass):
    """Test .yaml import when the inverter is inaccessible (e.g. darkness)."""
    TEST_DATA = {"device": "/dev/ttyUSB7", "address": 3, "name": "MyAuroraPV"}

    # First time round, no response.
    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError("No response after"),
    ) as mock_connect:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )

    configs = hass.config_entries.async_entries(DOMAIN)
    assert len(configs) == 1
    entry = configs[0]
    assert not entry.unique_id
    assert entry.state == ConfigEntryState.SETUP_RETRY

    assert len(mock_connect.mock_calls) == 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_PORT] == "/dev/ttyUSB7"
    assert result["data"][CONF_ADDRESS] == 3

    # Second time round, talking this time.
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
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=_simulated_returns,
    ):
        # Wait >5seconds for the config to auto retry.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=6))
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED
        assert entry.unique_id

        assert len(mock_connect.mock_calls) == 1
        assert hass.states.get("sensor.power_output").state == "45.7"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_import_night_then_user(hass):
    """Attempt yaml import and fail (dark), but user sets up manually before auto retry."""
    TEST_DATA = {"device": "/dev/ttyUSB7", "address": 3, "name": "MyAuroraPV"}

    # First time round, no response.
    with patch(
        "aurorapy.client.AuroraSerialClient.connect",
        side_effect=AuroraError("No response after"),
    ) as mock_connect:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=TEST_DATA
        )

    configs = hass.config_entries.async_entries(DOMAIN)
    assert len(configs) == 1
    entry = configs[0]
    assert not entry.unique_id
    assert entry.state == ConfigEntryState.SETUP_RETRY

    assert len(mock_connect.mock_calls) == 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_PORT] == "/dev/ttyUSB7"
    assert result["data"][CONF_ADDRESS] == 3

    # Failed once, now simulate the user initiating config flow with valid settings.
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/ttyUSB7", CONF_ADDRESS: 7},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    # Now retry yaml - it should fail with duplicate
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
    ):
        # Wait >5seconds for the config to auto retry.
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=6))
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
