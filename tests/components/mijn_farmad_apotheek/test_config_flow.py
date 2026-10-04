"""Test the Mijn Farmad Apotheek config flow."""

from unittest.mock import MagicMock

from aiofarmad import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadMfaRequiredError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.mijn_farmad_apotheek.const import (
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_ACCESS_TOKEN,
    API_ACCOUNT_FULL_NAME,
    API_ACCOUNT_ID,
    API_REFRESH_TOKEN,
    USER_INPUT,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(
    hass: HomeAssistant, mock_farmad_client_config_flow: MagicMock
) -> None:
    """Test a successful flow creates an entry that holds the token pair."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == API_ACCOUNT_FULL_NAME
    assert result["data"] == {
        CONF_ACCESS_TOKEN: API_ACCESS_TOKEN,
        CONF_REFRESH_TOKEN: API_REFRESH_TOKEN,
    }
    assert result["result"].unique_id == API_ACCOUNT_ID
    client = mock_farmad_client_config_flow.return_value
    client.async_login.assert_awaited_once()
    client.async_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            FarmadAuthenticationError("mock"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(FarmadMfaRequiredError("mock"), "mfa_required", id="mfa_required"),
        pytest.param(
            FarmadCommunicationError("mock"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(RuntimeError("mock"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    mock_farmad_client_config_flow: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the form shows the login error and recovers on the next attempt."""
    client = mock_farmad_client_config_flow.return_value
    client.async_login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_no_access_token(
    hass: HomeAssistant, mock_farmad_client_config_flow: MagicMock
) -> None:
    """Test the form shows invalid_auth without an access token and then recovers."""
    client = mock_farmad_client_config_flow.return_value
    client.access_token = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    client.access_token = API_ACCESS_TOKEN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_farmad_client_config_flow")
async def test_already_configured(hass: HomeAssistant) -> None:
    """Test the flow aborts when an entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
