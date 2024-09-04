"""Tests for the Iskra config flow."""

from pyiskra.exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    InvalidResponseCode,
    NotAuthorised,
)
import pytest

from homeassistant.components.iskra import DOMAIN
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

from .const import (
    HOST,
    MODBUS_ADDRESS,
    MODBUS_PORT,
    PASSWORD,
    PQ_MODEL,
    SERIAL,
    SG_MODEL,
    USERNAME,
)

from tests.common import MockConfigEntry


# Test step_user with Rest API protocol
async def test_user_rest_no_auth(hass: HomeAssistant, mock_pyiskra_rest) -> None:
    """Test the user flow with Rest API protocol."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Test if user form is provided
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test no authentication required
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    # Test successful Rest API configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{SG_MODEL} {SERIAL}"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PROTOCOL] == "rest_api"


async def test_user_rest_auth(hass: HomeAssistant, mock_pyiskra_rest) -> None:
    """Test the user flow with Rest API protocol and authentication required."""
    mock_pyiskra_rest.side_effect = NotAuthorised

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Test if user form is provided
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test if prompted to enter username and password if not authorised
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authentication"

    # Test failed authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["step_id"] == "authentication"

    # Test successful authentication
    mock_pyiskra_rest.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    # Test successful Rest API configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{SG_MODEL} {SERIAL}"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PROTOCOL] == "rest_api"
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_user_modbus(hass: HomeAssistant, mock_pyiskra_modbus) -> None:
    """Test the user flow with Modbus TCP protocol."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Test if user form is provided
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST, CONF_PROTOCOL: "modbus_tcp"},
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
    assert result["data"][CONF_PROTOCOL] == "modbus_tcp"
    assert result["data"][CONF_PORT] == MODBUS_PORT
    assert result["data"][CONF_ADDRESS] == MODBUS_ADDRESS


@pytest.mark.parametrize(
    ("protocol"),
    [
        ("rest_api"),
        ("modbus_tcp"),
    ],
)
async def test_abort_if_already_setup(
    hass: HomeAssistant, mock_pyiskra_rest, mock_pyiskra_modbus, protocol
) -> None:
    """Test we abort if Iskra is already setup."""

    MockConfigEntry(domain=DOMAIN, unique_id=SERIAL).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: protocol},
    )

    if protocol == "modbus_tcp":
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "modbus_tcp"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PORT: MODBUS_PORT,
                CONF_ADDRESS: MODBUS_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("protocol", "s_effect", "reason"),
    [
        ("rest_api", DeviceConnectionError, "cannot_connect"),
        ("rest_api", DeviceTimeoutError, "cannot_connect"),
        ("rest_api", InvalidResponseCode, "cannot_connect"),
        ("rest_api", Exception, "unknown"),
        ("modbus_tcp", DeviceConnectionError, "cannot_connect"),
        ("modbus_tcp", DeviceTimeoutError, "cannot_connect"),
        ("modbus_tcp", InvalidResponseCode, "cannot_connect"),
        ("modbus_tcp", Exception, "unknown"),
    ],
)
async def test_device_error(
    hass: HomeAssistant,
    mock_pyiskra_rest,
    mock_pyiskra_modbus,
    protocol,
    s_effect,
    reason,
) -> None:
    """Test device error with Modbus TCP protocol."""
    mock_pyiskra_modbus.side_effect = s_effect
    mock_pyiskra_rest.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: protocol},
    )

    if protocol == "modbus_tcp":
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "modbus_tcp"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PORT: MODBUS_PORT,
                CONF_ADDRESS: MODBUS_ADDRESS,
            },
        )

    # Test if error returned
    assert result["type"] is FlowResultType.FORM

    if protocol == "modbus_tcp":
        assert result["step_id"] == "modbus_tcp"
    elif protocol == "rest_api":
        assert result["step_id"] == "user"

    assert result["errors"] == {"base": reason}
