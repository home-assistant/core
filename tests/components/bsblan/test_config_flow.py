"""Tests for the BSBLan device config flow."""

from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANAuthError, BSBLANConnectionError

from homeassistant.components.bsblan import config_flow
from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan connection error."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("step_id") == "user"


async def test_authentication_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan authentication error with field preservation."""
    mock_bsblan.device.side_effect = BSBLANAuthError

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8080,
        CONF_PASSKEY: "secret",
        CONF_USERNAME: "testuser",
        CONF_PASSWORD: "wrongpassword",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}
    assert result.get("step_id") == "user"

    # Verify that user input is preserved in the form
    data_schema = result.get("data_schema")
    assert data_schema is not None

    # Check that the form fields contain the previously entered values
    host_field = next(
        field for field in data_schema.schema if field.schema == CONF_HOST
    )
    port_field = next(
        field for field in data_schema.schema if field.schema == CONF_PORT
    )
    passkey_field = next(
        field for field in data_schema.schema if field.schema == CONF_PASSKEY
    )
    username_field = next(
        field for field in data_schema.schema if field.schema == CONF_USERNAME
    )
    password_field = next(
        field for field in data_schema.schema if field.schema == CONF_PASSWORD
    )

    # The defaults are callable functions, so we need to call them
    assert host_field.default() == "192.168.1.100"
    assert port_field.default() == 8080
    assert passkey_field.default() == "secret"
    assert username_field.default() == "testuser"
    assert password_field.default() == "wrongpassword"


async def test_authentication_error_vs_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test that authentication and connection errors are handled differently."""
    # Test connection error first
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result_connection = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
        },
    )

    assert result_connection.get("errors") == {"base": "cannot_connect"}

    # Reset and test authentication error
    mock_bsblan.device.side_effect = BSBLANAuthError

    result_auth = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrongpass",
        },
    )

    assert result_auth.get("errors") == {"base": "invalid_auth"}


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort flow if BSBLAN device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
