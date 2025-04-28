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
    assert result["result"].unique_id == SERIAL
    assert result["title"] == SG_MODEL
    assert result["data"] == {CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"}


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
    assert result["result"].unique_id == SERIAL
    assert result["title"] == SG_MODEL
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PROTOCOL: "rest_api",
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }


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
    assert result["result"].unique_id == SERIAL
    assert result["title"] == PQ_MODEL
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PROTOCOL: "modbus_tcp",
        CONF_PORT: MODBUS_PORT,
        CONF_ADDRESS: MODBUS_ADDRESS,
    }


async def test_modbus_abort_if_already_setup(
    hass: HomeAssistant, mock_pyiskra_modbus
) -> None:
    """Test we abort if Iskra is already setup."""

    MockConfigEntry(domain=DOMAIN, unique_id=SERIAL).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_rest_api_abort_if_already_setup(
    hass: HomeAssistant, mock_pyiskra_rest
) -> None:
    """Test we abort if Iskra is already setup."""

    MockConfigEntry(domain=DOMAIN, unique_id=SERIAL).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
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
async def test_modbus_device_error(
    hass: HomeAssistant,
    mock_pyiskra_modbus,
    s_effect,
    reason,
) -> None:
    """Test device error with Modbus TCP protocol."""
    mock_pyiskra_modbus.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
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

    # Test if error returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "modbus_tcp"
    assert result["errors"] == {"base": reason}

    # Remove side effect
    mock_pyiskra_modbus.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PORT: MODBUS_PORT,
            CONF_ADDRESS: MODBUS_ADDRESS,
        },
    )

    # Test successful Modbus TCP configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == PQ_MODEL
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PROTOCOL: "modbus_tcp",
        CONF_PORT: MODBUS_PORT,
        CONF_ADDRESS: MODBUS_ADDRESS,
    }


@pytest.mark.parametrize(
    ("s_effect", "reason"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (DeviceTimeoutError, "cannot_connect"),
        (InvalidResponseCode, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_rest_device_error(
    hass: HomeAssistant,
    mock_pyiskra_rest,
    s_effect,
    reason,
) -> None:
    """Test device error with Modbus TCP protocol."""
    mock_pyiskra_rest.side_effect = s_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    # Test if error returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": reason}

    # Remove side effect
    mock_pyiskra_rest.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"},
    )

    # Test successful Rest API configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == SG_MODEL
    assert result["data"] == {CONF_HOST: HOST, CONF_PROTOCOL: "rest_api"}
