"""Test the Nibe Heat Pump config flow."""
from unittest.mock import Mock

from nibe.coil import Coil
from nibe.exceptions import (
    AddressInUseException,
    CoilNotFoundException,
    ReadException,
    ReadSendException,
    WriteException,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.nibe_heatpump import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_FLOW_NIBEGW_USERDATA = {
    "model": "F1155",
    "ip_address": "127.0.0.1",
    "listening_port": 9999,
    "remote_read_port": 10000,
    "remote_write_port": 10001,
}


MOCK_FLOW_MODBUS_USERDATA = {
    "model": "S1155",
    "modbus_url": "tcp://127.0.0.1",
    "modbus_unit": 0,
}


pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _get_connection_form(
    hass: HomeAssistant, connection_type: str
) -> FlowResultType:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    return result


async def test_nibegw_form(
    hass: HomeAssistant, mock_connection: Mock, mock_setup_entry: Mock
) -> None:
    """Test we get the form."""
    result = await _get_connection_form(hass, "nibegw")

    coil_wordswap = Coil(
        48852, "modbus40-word-swap-48852", "Modbus40 Word Swap", "u8", min=0, max=1
    )
    coil_wordswap.value = "ON"
    mock_connection.read_coil.return_value = coil_wordswap

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_NIBEGW_USERDATA
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "F1155 at 127.0.0.1"
    assert result2["data"] == {
        "model": "F1155",
        "ip_address": "127.0.0.1",
        "listening_port": 9999,
        "remote_read_port": 10000,
        "remote_write_port": 10001,
        "word_swap": True,
        "connection_type": "nibegw",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_modbus_form(
    hass: HomeAssistant, mock_connection: Mock, mock_setup_entry: Mock
) -> None:
    """Test we get the form."""
    result = await _get_connection_form(hass, "modbus")

    coil = Coil(
        40022, "reset-alarm-40022", "Reset Alarm", "u8", min=0, max=1, write=True
    )
    coil.value = "ON"
    mock_connection.read_coil.return_value = coil

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_MODBUS_USERDATA
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "S1155 at 127.0.0.1"
    assert result2["data"] == {
        "model": "S1155",
        "modbus_url": "tcp://127.0.0.1",
        "modbus_unit": 0,
        "connection_type": "modbus",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_modbus_invalid_url(
    hass: HomeAssistant, mock_connection_constructor: Mock
) -> None:
    """Test we handle invalid auth."""
    result = await _get_connection_form(hass, "modbus")

    mock_connection_constructor.side_effect = ValueError()
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_FLOW_MODBUS_USERDATA, "modbus_url": "invalid://url"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"modbus_url": "url"}


async def test_nibegw_address_inuse(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle invalid auth."""
    result = await _get_connection_form(hass, "nibegw")

    mock_connection.start.side_effect = AddressInUseException()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_NIBEGW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"listening_port": "address_in_use"}

    mock_connection.start.side_effect = Exception()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_NIBEGW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("connection_type", "data"),
    (
        ("nibegw", MOCK_FLOW_NIBEGW_USERDATA),
        ("modbus", MOCK_FLOW_MODBUS_USERDATA),
    ),
)
async def test_read_timeout(
    hass: HomeAssistant, mock_connection: Mock, connection_type: str, data: dict
) -> None:
    """Test we handle cannot connect error."""
    result = await _get_connection_form(hass, connection_type)

    mock_connection.verify_connectivity.side_effect = ReadException()

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "read"}


@pytest.mark.parametrize(
    ("connection_type", "data"),
    (
        ("nibegw", MOCK_FLOW_NIBEGW_USERDATA),
        ("modbus", MOCK_FLOW_MODBUS_USERDATA),
    ),
)
async def test_write_timeout(
    hass: HomeAssistant, mock_connection: Mock, connection_type: str, data: dict
) -> None:
    """Test we handle cannot connect error."""
    result = await _get_connection_form(hass, connection_type)

    mock_connection.verify_connectivity.side_effect = WriteException()

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "write"}


@pytest.mark.parametrize(
    ("connection_type", "data"),
    (
        ("nibegw", MOCK_FLOW_NIBEGW_USERDATA),
        ("modbus", MOCK_FLOW_MODBUS_USERDATA),
    ),
)
async def test_unexpected_exception(
    hass: HomeAssistant, mock_connection: Mock, connection_type: str, data: dict
) -> None:
    """Test we handle cannot connect error."""
    result = await _get_connection_form(hass, connection_type)

    mock_connection.verify_connectivity.side_effect = Exception()

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("connection_type", "data"),
    (
        ("nibegw", MOCK_FLOW_NIBEGW_USERDATA),
        ("modbus", MOCK_FLOW_MODBUS_USERDATA),
    ),
)
async def test_nibegw_invalid_host(
    hass: HomeAssistant, mock_connection: Mock, connection_type: str, data: dict
) -> None:
    """Test we handle cannot connect error."""
    result = await _get_connection_form(hass, connection_type)

    mock_connection.verify_connectivity.side_effect = ReadSendException()

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result2["type"] == FlowResultType.FORM
    if connection_type == "nibegw":
        assert result2["errors"] == {"ip_address": "address"}
    else:
        assert result2["errors"] == {"modbus_url": "address"}


@pytest.mark.parametrize(
    ("connection_type", "data"),
    (
        ("nibegw", MOCK_FLOW_NIBEGW_USERDATA),
        ("modbus", MOCK_FLOW_MODBUS_USERDATA),
    ),
)
async def test_model_missing_coil(
    hass: HomeAssistant, mock_connection: Mock, connection_type: str, data: dict
) -> None:
    """Test we handle cannot connect error."""
    result = await _get_connection_form(hass, connection_type)

    mock_connection.verify_connectivity.side_effect = CoilNotFoundException()

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "model"}
