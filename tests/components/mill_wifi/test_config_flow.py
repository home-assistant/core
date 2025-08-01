"""Tests for the Mill WiFi config flow."""

from unittest.mock import AsyncMock, patch

from custom_components.mill_wifi.api import AuthenticationError, MillApiError
from custom_components.mill_wifi.const import DOMAIN
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

# Mock data for user input
MOCK_USER_INPUT = {
    CONF_USERNAME: "test_user",
    CONF_PASSWORD: "test_password",
}

MOCK_USER_INPUT_WRONG_PW = {
    CONF_USERNAME: "test_user",
    CONF_PASSWORD: "wrong_password",
}


async def test_form_show_initial(hass: HomeAssistant) -> None:
    """Test that the initial configuration form is shown correctly.

    Actions: Initiate the config flow for the user step.
             The pytest-homeassistant-custom-component plugin should make the integration discoverable.
    Expected Outcome: The flow result should be of type FORM, for the 'user' step.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result is not None
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert (
        result["errors"] is None or result["errors"] == {}
    )
    assert "flow_id" in result

    # Check if the schema contains the expected fields
    schema = result["data_schema"].schema
    assert CONF_USERNAME in schema
    assert CONF_PASSWORD in schema


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Purpose: Test the user step of the config flow with valid credentials."""

    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == data_entry_flow.FlowResultType.FORM
    assert result_init["step_id"] == "user"

    with patch(
        "custom_components.mill_wifi.config_flow.MillApiClient", autospec=True
    ) as mock_api_client_class:
        mock_api_instance = mock_api_client_class.return_value
        mock_api_instance.async_setup = AsyncMock(return_value=None)
        mock_api_instance.login = AsyncMock(return_value=None)

        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result_configure is not None
    assert result_configure["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == "Mill WiFi"
    assert result_configure["data"] == MOCK_USER_INPUT
    mock_api_instance.async_setup.assert_called_once()
    mock_api_instance.login.assert_called_once()


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Purpose: Test the user step with invalid credentials."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.mill_wifi.config_flow.MillApiClient", autospec=True
    ) as mock_api_client_class:
        mock_api_instance = mock_api_client_class.return_value
        mock_api_instance.async_setup = AsyncMock(return_value=None)
        mock_api_instance.login = AsyncMock(
            side_effect=AuthenticationError("Test Auth Error")
        )

        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            MOCK_USER_INPUT_WRONG_PW,
        )
        await hass.async_block_till_done()

    assert result_configure is not None
    assert result_configure["type"] == data_entry_flow.FlowResultType.FORM
    assert result_configure["step_id"] == "user"
    assert result_configure["errors"] == {"base": "invalid_auth"}
    mock_api_instance.async_setup.assert_called_once()
    mock_api_instance.login.assert_called_once()


async def test_user_step_api_error_on_login(hass: HomeAssistant) -> None:
    """Purpose: Test user step when API login raises MillApiError."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.mill_wifi.config_flow.MillApiClient", autospec=True
    ) as mock_api_client_class:
        mock_api_instance = mock_api_client_class.return_value
        mock_api_instance.async_setup = AsyncMock(return_value=None)
        mock_api_instance.login = AsyncMock(
            side_effect=MillApiError("Test API Error on login")
        )

        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result_configure is not None
    assert result_configure["type"] == data_entry_flow.FlowResultType.FORM
    assert result_configure["step_id"] == "user"
    assert result_configure["errors"] == {"base": "invalid_auth"}
    mock_api_instance.async_setup.assert_called_once()
    mock_api_instance.login.assert_called_once()


async def test_user_step_api_error_on_async_setup(hass: HomeAssistant) -> None:
    """Purpose: Test user step when MillApiClient.async_setup fails."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.mill_wifi.config_flow.MillApiClient", autospec=True
    ) as mock_api_client_class:
        mock_api_instance = mock_api_client_class.return_value
        mock_api_instance.async_setup = AsyncMock(
            side_effect=MillApiError("Failed to setup client")
        )

        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result_configure is not None
    assert result_configure["type"] == data_entry_flow.FlowResultType.FORM
    assert result_configure["step_id"] == "user"
    assert result_configure["errors"] == {"base": "invalid_auth"}
    mock_api_instance.async_setup.assert_called_once()
    mock_api_instance.login.assert_not_called()


@pytest.mark.skip(
    reason="Reauth flow not explicitly implemented in the provided config_flow.py"
)
async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauthentication flow."""
    pass  # noqa: PIE790
