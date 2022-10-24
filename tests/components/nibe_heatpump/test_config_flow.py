"""Test the Nibe Heat Pump config flow."""
import errno
from socket import gaierror
from unittest.mock import Mock, patch

from nibe.coil import Coil
from nibe.connection import Connection
from nibe.exceptions import CoilNotFoundException, CoilReadException, CoilWriteException
from pytest import fixture

from homeassistant import config_entries
from homeassistant.components.nibe_heatpump import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_FLOW_USERDATA = {
    "model": "F1155",
    "ip_address": "127.0.0.1",
    "listening_port": 9999,
    "remote_read_port": 10000,
    "remote_write_port": 10001,
}


@fixture(autouse=True, name="mock_connection")
async def fixture_mock_connection():
    """Make sure we have a dummy connection."""
    with patch(
        "homeassistant.components.nibe_heatpump.config_flow.NibeGW", spec=Connection
    ) as mock_connection:
        yield mock_connection


@fixture(autouse=True, name="mock_setup_entry")
async def fixture_mock_setup():
    """Make sure we never actually run setup."""
    with patch(
        "homeassistant.components.nibe_heatpump.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_form(
    hass: HomeAssistant, mock_connection: Mock, mock_setup_entry: Mock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    coil_wordswap = Coil(
        48852, "modbus40-word-swap-48852", "Modbus40 Word Swap", "u8", min=0, max=1
    )
    coil_wordswap.value = "ON"
    mock_connection.return_value.read_coil.return_value = coil_wordswap

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
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


async def test_address_inuse(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    error = OSError()
    error.errno = errno.EADDRINUSE
    mock_connection.return_value.start.side_effect = error

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"listening_port": "address_in_use"}

    error.errno = errno.EACCES
    mock_connection.return_value.start.side_effect = error

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_read_timeout(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_connection.return_value.read_coil.side_effect = CoilReadException()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "read"}


async def test_write_timeout(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_connection.return_value.write_coil.side_effect = CoilWriteException()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "write"}


async def test_unexpected_exception(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_connection.return_value.read_coil.side_effect = Exception()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_FLOW_USERDATA
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_invalid_host(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_connection.return_value.read_coil.side_effect = gaierror()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_FLOW_USERDATA, "ip_address": "abcd"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"ip_address": "address"}


async def test_model_missing_coil(hass: HomeAssistant, mock_connection: Mock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_connection.return_value.read_coil.side_effect = CoilNotFoundException()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_FLOW_USERDATA}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "model"}
