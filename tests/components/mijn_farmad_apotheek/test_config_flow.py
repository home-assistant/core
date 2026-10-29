"""Test the Mijn Farmad Apotheek config flow."""

from unittest.mock import MagicMock

from aiofarmad import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadMfaRequiredError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.mijn_farmad_apotheek.const import (
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_ACCESS_TOKEN,
    API_ACCOUNT_EMAIL,
    API_ACCOUNT_FULL_NAME,
    API_ACCOUNT_ID,
    API_OTP,
    API_OTP_2,
    ENTRY_DATA,
    USER_INPUT,
    get_mock_account,
)

REAUTH_INPUT = {CONF_PASSWORD: "mock-password"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
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
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == API_ACCOUNT_ID
    client = mock_farmad_client.return_value
    client.async_login.assert_awaited_once()
    client.async_close.assert_awaited_once()
    assert mock_farmad_client.call_args.kwargs["otp_provider"] is None


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            FarmadAuthenticationError("mock"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            FarmadCommunicationError("mock"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(RuntimeError("mock"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the form shows the login error and recovers on the next attempt."""
    client = mock_farmad_client.return_value
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
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test the form shows invalid_auth without an access token and then recovers."""
    client = mock_farmad_client.return_value
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_mfa(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test a two-factor account asks for the code and then creates the entry."""
    client = mock_farmad_client.return_value
    client.async_login.side_effect = [FarmadMfaRequiredError("mock"), None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: API_OTP}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == API_ACCOUNT_FULL_NAME
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == API_ACCOUNT_ID
    provider = mock_farmad_client.call_args.kwargs["otp_provider"]
    assert await provider() == API_OTP


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(
            FarmadAuthenticationError("mock"),
            {CONF_CODE: "wrong_code"},
            id="wrong_code",
        ),
        pytest.param(
            FarmadCommunicationError("mock"),
            {"base": "cannot_connect"},
            id="cannot_connect",
        ),
        pytest.param(RuntimeError("mock"), {"base": "unknown"}, id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_mfa_errors(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    side_effect: Exception,
    errors: dict[str, str],
) -> None:
    """Test the code step shows the error and recovers on the next attempt."""
    client = mock_farmad_client.return_value
    client.async_login.side_effect = [FarmadMfaRequiredError("mock"), side_effect]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: API_OTP}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == errors

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: API_OTP_2}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_farmad_client")
async def test_already_configured(hass: HomeAssistant) -> None:
    """Test the flow aborts when an entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test reauthentication asks only the password and renews the token pair."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    client = mock_farmad_client.return_value
    client.access_token = "new-access-token"
    client.refresh_token = "new-refresh-token"

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["description_placeholders"]["account"] == API_ACCOUNT_EMAIL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_farmad_client.call_args.kwargs["email"] == API_ACCOUNT_EMAIL
    assert entry.data == {
        CONF_EMAIL: API_ACCOUNT_EMAIL,
        CONF_ACCESS_TOKEN: "new-access-token",
        CONF_REFRESH_TOKEN: "new-refresh-token",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_mfa(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test reauthentication of an account with two-factor authentication."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    client = mock_farmad_client.return_value
    client.async_login.side_effect = [FarmadMfaRequiredError("mock"), None]

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: API_OTP}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_farmad_client.call_args.kwargs["email"] == API_ACCOUNT_EMAIL
    assert entry.data == ENTRY_DATA


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            FarmadAuthenticationError("mock"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            FarmadCommunicationError("mock"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(RuntimeError("mock"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the reauthentication form shows the login error and recovers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    client = mock_farmad_client.return_value
    client.async_login.side_effect = side_effect

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_wrong_account(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test reauthentication aborts for the credentials of another account."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    mock_farmad_client.return_value.async_get_account.return_value = get_mock_account(
        account_id="auth0|other-account"
    )

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_without_refresh_token(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test reauthentication keeps the refresh token when login returns none."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=API_ACCOUNT_ID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    mock_farmad_client.return_value.refresh_token = None

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == ENTRY_DATA
