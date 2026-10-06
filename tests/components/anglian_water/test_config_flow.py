"""Test the Anglian Water config flow."""

from unittest.mock import AsyncMock

from pyanglianwater.exceptions import (
    ConsentRequiredError,
    ExpiredAccessTokenError,
    InvalidAccountIdError,
    MFARequiredError,
    SelfAssertedError,
    SmartMeterUnavailableError,
    UnknownEndpointError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.anglian_water.const import CONF_ACCOUNT_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CODE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ACCESS_TOKEN, ACCOUNT_NUMBER, PASSWORD, USERNAME

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.usefixtures("mock_setup_entry")
async def test_multiple_account_flow(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test the config flow when there are multiple accounts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.usefixtures("mock_setup_entry")
async def test_single_account_flow(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test the config flow when there is just a single account."""
    mock_anglian_water_client.api.get_associated_accounts.return_value = (
        await async_load_json_object_fixture(
            hass, "single_associated_accounts.json", DOMAIN
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.usefixtures("mock_setup_entry")
async def test_single_account_flow_with_mfa(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test the config flow when there is just a single account with MFA required."""
    mock_anglian_water_client.api.get_associated_accounts.return_value = (
        await async_load_json_object_fixture(
            hass, "single_associated_accounts.json", DOMAIN
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_authenticator.send_login_request.side_effect = MFARequiredError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (MFARequiredError, "invalid_code"),
        (ValueError, "unknown"),
    ],
)
async def test_single_account_flow_with_mfa_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type,
    expected_error,
) -> None:
    """Test the config flow when there is just a single account with MFA required and an exception is raised."""
    mock_anglian_water_client.api.get_associated_accounts.return_value = (
        await async_load_json_object_fixture(
            hass, "single_associated_accounts.json", DOMAIN
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_authenticator.send_login_request.side_effect = MFARequiredError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    mock_anglian_water_authenticator.send_mfa_request.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == {"base": expected_error}

    mock_anglian_water_authenticator.send_mfa_request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (ExpiredAccessTokenError, "cannot_connect"),
        (
            UnknownEndpointError(status=500, response="Service Unavailable"),
            "cannot_connect",
        ),
        (ValueError, "unknown"),
    ],
)
async def test_account_fetch_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type: Exception,
    expected_error: str,
) -> None:
    """Test that the flow handles account-fetch exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_client.api.get_associated_accounts.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (ExpiredAccessTokenError, "cannot_connect"),
        (
            UnknownEndpointError(status=500, response="Service Unavailable"),
            "cannot_connect",
        ),
        (ValueError, "unknown"),
    ],
)
async def test_mfa_account_fetch_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type: Exception,
    expected_error: str,
) -> None:
    """Test that the MFA flow handles account-fetch exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_authenticator.send_login_request.side_effect = MFARequiredError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    mock_anglian_water_client.api.get_associated_accounts.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test that the flow aborts when the entry is already added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (SelfAssertedError, "invalid_auth"),
        (ValueError, "unknown"),
        (ConsentRequiredError, "consent_required"),
    ],
)
async def test_auth_recover_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type,
    expected_error,
) -> None:
    """Test that the flow can recover from an auth exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_authenticator.send_login_request.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Now test we can recover

    mock_anglian_water_authenticator.send_login_request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (SmartMeterUnavailableError, "smart_meter_unavailable"),
        (InvalidAccountIdError, "smart_meter_unavailable"),
    ],
)
async def test_account_recover_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type,
    expected_error,
) -> None:
    """Test that the flow can recover from an account related exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    mock_anglian_water_client.validate_smart_meter.side_effect = exception_type

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_account"
    assert result["errors"] == {"base": expected_error}

    # Now test we can recover

    mock_anglian_water_client.validate_smart_meter.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    mock_anglian_water_authenticator.refresh_token = "new_access_token"
    original_data = dict(mock_config_entry.data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        **original_data,
        CONF_ACCESS_TOKEN: "new_access_token",
    }


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (SelfAssertedError, "invalid_auth"),
        (ConsentRequiredError, "consent_required"),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_flow_auth_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type: type[Exception],
    expected_error: str,
) -> None:
    """Test that the reauth flow can recover from an auth exception."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_anglian_water_authenticator.send_login_request.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_anglian_water_authenticator.send_login_request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_account_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test that reauth does not update an entry for another account."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    mock_anglian_water_client.api.get_associated_accounts.return_value = {
        "result": {"active": []}
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result is not None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "account_not_found"}
    assert mock_config_entry.data == original_data

    mock_anglian_water_client.api.get_associated_accounts.return_value = (
        await async_load_json_object_fixture(
            hass, "multi_associated_accounts.json", DOMAIN
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_mfa_required(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test the reauth flow with MFA required."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_anglian_water_authenticator.send_login_request.side_effect = MFARequiredError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (MFARequiredError, "invalid_code"),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_flow_mfa_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type: type[Exception],
    expected_error: str,
) -> None:
    """Test that the reauth flow can recover from an MFA exception."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_anglian_water_authenticator.send_login_request.side_effect = MFARequiredError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_mfa"

    mock_anglian_water_authenticator.send_mfa_request.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_mfa"
    assert result["errors"] == {"base": expected_error}

    mock_anglian_water_authenticator.send_mfa_request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (ExpiredAccessTokenError, "cannot_connect"),
        (
            UnknownEndpointError(status=500, response="Service Unavailable"),
            "cannot_connect",
        ),
        (ValueError, "unknown"),
    ],
)
async def test_reauth_flow_account_fetch_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test that reauth handles account-fetch exceptions."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    mock_anglian_water_client.api.get_associated_accounts.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data == original_data
