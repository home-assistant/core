"""Test the AirPatrol config flow."""

from airpatrol.api import AirPatrolAuthenticationError, AirPatrolError

from homeassistant import config_entries
from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "test_password",
}


async def test_async_step_reauth_confirm_success(
    hass: HomeAssistant, mock_config_entry, mock_api_authentication
) -> None:
    """Test successful reauthentication via async_step_reauth_confirm."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_config_entry.entry_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.data[CONF_PASSWORD] == "test_password"
    assert entry.data[CONF_ACCESS_TOKEN] == "test_access_token"


async def test_async_step_reauth_confirm_invalid_auth(
    hass: HomeAssistant, mock_config_entry, mock_api_authentication
) -> None:
    """Test reauthentication failure due to invalid credentials."""
    mock_api_authentication.side_effect = AirPatrolAuthenticationError("fail")
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_config_entry.entry_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_success(hass: HomeAssistant, mock_api_authentication) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USER_INPUT[CONF_EMAIL]
    assert result["data"] == {
        **TEST_USER_INPUT,
        CONF_ACCESS_TOKEN: "test_access_token",
    }
    assert result["result"].unique_id == "test_user_id"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_api_authentication,
) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_api_authentication.side_effect = AirPatrolAuthenticationError(
        "Authentication failed"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_connection_error(
    hass: HomeAssistant, mock_api_authentication
) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_api_authentication.side_effect = Exception("Connection failed")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_api_authentication
) -> None:
    """Test user flow when already configured."""
    # Create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=mock_api_authentication.return_value.get_unique_id(),
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_api_authentication
) -> None:
    """Test user flow with AirPatrolError error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    mock_api_authentication.side_effect = AirPatrolError("fail")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth_error(
    hass: HomeAssistant, mock_api_authentication
) -> None:
    """Test user flow with AirPatrolAuthenticationError error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    mock_api_authentication.side_effect = AirPatrolAuthenticationError("fail")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
