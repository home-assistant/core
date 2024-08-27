"""Tests for the Iskra config flow."""

from unittest.mock import patch

from pyiskra.exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    InvalidResponseCode,
    NotAuthorised,
)
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SG_MODEL = "SG-W1"
PQ_MODEL = "MC784"
SERIAL = "XXXXXXX"
HOST = "192.1.0.1"
MODBUS_PORT = 10001
MODBUS_ADDRESS = 33


class MockBasicInfo:
    """Mock BasicInfo class."""

    def __init__(self, model):
        """Initialize the mock class."""
        self.serial = SERIAL
        self.model = model
        self.description = "Iskra mock device"
        self.location = "imagination"
        self.sw_ver = "1.0.0"


@pytest.fixture
def mock_pyiskra_rest():
    """Mock Iskra API authenticate with Rest API protocol."""

    with patch(
        "pyiskra.adapters.RestAPI.RestAPI.get_basic_info",
        return_value=MockBasicInfo(model=SG_MODEL),
    ) as basic_info_mock:
        yield basic_info_mock


@pytest.fixture
def mock_pyiskra_modbus():
    """Mock Iskra API authenticate with Rest API protocol."""

    with patch(
        "pyiskra.adapters.Modbus.Modbus.get_basic_info",
        return_value=MockBasicInfo(model=PQ_MODEL),
    ) as basic_info_mock:
        yield basic_info_mock


# Test step_user with Rest API protocol
async def test_user_rest_no_auth(hass: HomeAssistant, mock_pyiskra_rest) -> None:
    """Test the user flow with Rest API protocol."""

    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test no authentication required
    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    # Test successful Rest API configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{SG_MODEL} {SERIAL}"
    assert result["data"][CONF_HOST] == HOST


async def test_user_rest_auth(hass: HomeAssistant, mock_pyiskra_rest) -> None:
    """Test the user flow with Rest API protocol and authentication required."""
    mock_pyiskra_rest.side_effect = NotAuthorised

    # Test if prompted to enter username and password if not authorised
    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authentication"

    # Test failed authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "", CONF_PASSWORD: ""},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "authentication"

    # Test successful authentication
    mock_pyiskra_rest.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "", CONF_PASSWORD: ""},
    )

    # Test successful Rest API configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{SG_MODEL} {SERIAL}"
    assert result["data"][CONF_HOST] == HOST


async def test_user_modbus(hass: HomeAssistant, mock_pyiskra_modbus) -> None:
    """Test the user flow with Modbus TCP protocol."""

    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "modbus_tcp"},
    )

    # Test if propmpted to enter port and address
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "modbus_tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PORT: MODBUS_PORT,
            CONF_ADDRESS: MODBUS_ADDRESS,
        },
    )

    # Test successful Modbus TCP configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{PQ_MODEL} {SERIAL}"
    assert result["data"][CONF_HOST] == HOST


async def test_abort_if_already_setup(hass: HomeAssistant, mock_pyiskra_rest) -> None:
    """Test we abort if Iskra is already setup."""

    MockConfigEntry(domain="iskra", unique_id=SERIAL).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("s_effect", "reason"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (DeviceTimeoutError, "cannot_connect"),
        (InvalidResponseCode, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_device_abort_rest(
    hass: HomeAssistant, mock_pyiskra_rest, s_effect, reason
) -> None:
    """Test device abort with Rest API protocol."""
    mock_pyiskra_rest.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    # Test if aborted
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("s_effect", "reason"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (DeviceTimeoutError, "cannot_connect"),
        (InvalidResponseCode, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_device_abort_modbus(
    hass: HomeAssistant, mock_pyiskra_modbus, s_effect, reason
) -> None:
    """Test device abort with Modbus TCP protocol."""
    mock_pyiskra_modbus.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        "iskra",
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "modbus_tcp"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "modbus_tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PORT: MODBUS_PORT,
            CONF_ADDRESS: MODBUS_ADDRESS,
        },
    )

    # Test if aborted
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["step_id"] == "modbus_tcp"
