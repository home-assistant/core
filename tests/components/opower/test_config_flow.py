"""Test the Opower config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from opower import CannotConnect, InvalidAuth, MfaChallenge
import pytest

from homeassistant import config_entries
from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opower.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock]:
    """Mock unloading a config entry."""
    with patch(
        "homeassistant.components.opower.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        yield mock_unload_entry


async def test_form(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select utility
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"

    # Enter credentials
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Pacific Gas and Electric Company (PG&E) (test-username)"
    assert result3["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_with_totp(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we can configure a utility that accepts a TOTP secret."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select utility
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Consolidated Edison (ConEd)"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"

    # Enter credentials
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "totp_secret": "test-totp",
            },
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Consolidated Edison (ConEd) (test-username)"
    assert result3["data"] == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "test-password",
        "totp_secret": "test-totp",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_with_invalid_totp(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle an invalid TOTP secret."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Consolidated Edison (ConEd)"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "credentials"

    # Enter invalid credentials
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=InvalidAuth,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "totp_secret": "bad-totp",
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}
    assert result3["step_id"] == "credentials"

    # Enter valid credentials
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "updated-password",
                "totp_secret": "good-totp",
            },
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Consolidated Edison (ConEd) (test-username)"
    assert result4["data"] == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "updated-password",
        "totp_secret": "good-totp",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_with_mfa_challenge(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the full interactive MFA flow, including error recovery."""
    # 1. Start the flow and get to the credentials step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )

    # 2. Trigger an MfaChallenge on login
    mock_mfa_handler = AsyncMock()
    mock_mfa_handler.async_get_mfa_options.return_value = {
        "Email": "fooxxx@mail.com",
        "Phone": "xxx-123",
    }
    mock_mfa_handler.async_submit_mfa_code.return_value = {
        "login_data_mock_key": "login_data_mock_value"
    }
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=MfaChallenge(message="", handler=mock_mfa_handler),
    ) as mock_login:
        result_challenge = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        mock_login.assert_awaited_once()

    # 3. Handle the MFA options step, starting with a connection error
    assert result_challenge["type"] is FlowResultType.FORM
    assert result_challenge["step_id"] == "mfa_options"
    mock_mfa_handler.async_get_mfa_options.assert_awaited_once()

    # Test CannotConnect on selecting MFA method
    mock_mfa_handler.async_select_mfa_option.side_effect = CannotConnect
    result_mfa_connect_fail = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_method": "Email"}
    )
    mock_mfa_handler.async_select_mfa_option.assert_awaited_once_with("Email")
    assert result_mfa_connect_fail["type"] is FlowResultType.FORM
    assert result_mfa_connect_fail["step_id"] == "mfa_options"
    assert result_mfa_connect_fail["errors"] == {"base": "cannot_connect"}

    # Retry selecting MFA method successfully
    mock_mfa_handler.async_select_mfa_option.side_effect = None
    result_mfa_select_ok = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_method": "Email"}
    )
    assert mock_mfa_handler.async_select_mfa_option.call_count == 2
    assert result_mfa_select_ok["type"] is FlowResultType.FORM
    assert result_mfa_select_ok["step_id"] == "mfa_code"

    # 4. Handle the MFA code step, testing multiple failure scenarios
    # Test InvalidAuth on submitting code
    mock_mfa_handler.async_submit_mfa_code.side_effect = InvalidAuth
    result_mfa_invalid_code = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_code": "bad-code"}
    )
    mock_mfa_handler.async_submit_mfa_code.assert_awaited_once_with("bad-code")
    assert result_mfa_invalid_code["type"] is FlowResultType.FORM
    assert result_mfa_invalid_code["step_id"] == "mfa_code"
    assert result_mfa_invalid_code["errors"] == {"base": "invalid_mfa_code"}

    # Test CannotConnect on submitting code
    mock_mfa_handler.async_submit_mfa_code.side_effect = CannotConnect
    result_mfa_code_connect_fail = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_code": "good-code"}
    )
    assert mock_mfa_handler.async_submit_mfa_code.call_count == 2
    mock_mfa_handler.async_submit_mfa_code.assert_called_with("good-code")
    assert result_mfa_code_connect_fail["type"] is FlowResultType.FORM
    assert result_mfa_code_connect_fail["step_id"] == "mfa_code"
    assert result_mfa_code_connect_fail["errors"] == {"base": "cannot_connect"}

    # Retry submitting code successfully
    mock_mfa_handler.async_submit_mfa_code.side_effect = None
    result_final = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_code": "good-code"}
    )
    assert mock_mfa_handler.async_submit_mfa_code.call_count == 3
    mock_mfa_handler.async_submit_mfa_code.assert_called_with("good-code")

    # 5. Verify the flow completes and creates the entry
    assert result_final["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result_final["title"]
        == "Pacific Gas and Electric Company (PG&E) (test-username)"
    )
    assert result_final["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password",
        "login_data": {"login_data_mock_key": "login_data_mock_value"},
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_mfa_challenge_but_no_mfa_options(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the full interactive MFA flow when there are no MFA options."""
    # 1. Start the flow and get to the credentials step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )

    # 2. Trigger an MfaChallenge on login
    mock_mfa_handler = AsyncMock()
    mock_mfa_handler.async_get_mfa_options.return_value = {}
    mock_mfa_handler.async_submit_mfa_code.return_value = {
        "login_data_mock_key": "login_data_mock_value"
    }
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=MfaChallenge(message="", handler=mock_mfa_handler),
    ) as mock_login:
        result_challenge = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        mock_login.assert_awaited_once()

    # 3. No MFA options. Handle the MFA code step
    assert result_challenge["type"] is FlowResultType.FORM
    assert result_challenge["step_id"] == "mfa_code"
    mock_mfa_handler.async_get_mfa_options.assert_awaited_once()
    result_final = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_code": "good-code"}
    )
    mock_mfa_handler.async_submit_mfa_code.assert_called_with("good-code")

    # 4. Verify the flow completes and creates the entry
    assert result_final["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result_final["title"]
        == "Pacific Gas and Electric Company (PG&E) (test-username)"
    )
    assert result_final["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password",
        "login_data": {"login_data_mock_key": "login_data_mock_value"},
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("api_exception", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
    ],
)
async def test_form_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    api_exception: Exception,
    expected_error: str,
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=api_exception,
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}
    # On error, the form should have the previous user input as suggested values.
    data_schema = result2["data_schema"].schema
    assert get_schema_suggested_value(data_schema, "username") == "test-username"
    assert get_schema_suggested_value(data_schema, "password") == "test-password"
    assert mock_login.call_count == 1


async def test_form_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert mock_login.call_count == 0


async def test_form_not_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user input for config_entry different than the existing one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"utility": "Pacific Gas and Electric Company (PG&E)"},
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username2",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result2["title"] == "Pacific Gas and Electric Company (PG&E) (test-username2)"
    )
    assert result2["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username2",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 2
    assert mock_login.call_count == 1


async def test_form_valid_reauth(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we can handle a valid reauth."""
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["title_placeholders"] == {"name": mock_config_entry.title}

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["data_schema"].schema.keys() == {
            "username",
            "password",
        }

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password2"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    assert mock_config_entry.data == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password2",
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_valid_reauth_with_totp(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test that we can handle a valid reauth for a utility with TOTP."""
    mock_config_entry = MockConfigEntry(
        title="Consolidated Edison (ConEd) (test-username)",
        domain=DOMAIN,
        data={
            "utility": "Consolidated Edison (ConEd)",
            "username": "test-username",
            "password": "test-password",
        },
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["data_schema"].schema.keys() == {
            "username",
            "password",
            "totp_secret",
        }

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password2",
                "totp_secret": "test-totp",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    assert mock_config_entry.data == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "test-password2",
        "totp_secret": "test-totp",
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_reauth_with_mfa_challenge(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full interactive MFA flow during reauth."""
    # 1. Set up the existing entry and trigger reauth
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    # 2. Test failure before MFA challenge (InvalidAuth)
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=InvalidAuth,
    ) as mock_login_fail_auth:
        result_invalid_auth = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "bad-password",
            },
        )
    mock_login_fail_auth.assert_awaited_once()
    assert result_invalid_auth["type"] is FlowResultType.FORM
    assert result_invalid_auth["step_id"] == "reauth_confirm"
    assert result_invalid_auth["errors"] == {"base": "invalid_auth"}

    # 3. Test failure before MFA challenge (CannotConnect)
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=CannotConnect,
    ) as mock_login_fail_connect:
        result_cannot_connect = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-password",
            },
        )
    mock_login_fail_connect.assert_awaited_once()
    assert result_cannot_connect["type"] is FlowResultType.FORM
    assert result_cannot_connect["step_id"] == "reauth_confirm"
    assert result_cannot_connect["errors"] == {"base": "cannot_connect"}

    # 4. Trigger the MfaChallenge on the next attempt
    mock_mfa_handler = AsyncMock()
    mock_mfa_handler.async_get_mfa_options.return_value = {
        "Email": "fooxxx@mail.com",
        "Phone": "xxx-123",
    }
    mock_mfa_handler.async_submit_mfa_code.return_value = {
        "login_data_mock_key": "login_data_mock_value"
    }
    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=MfaChallenge(message="", handler=mock_mfa_handler),
    ) as mock_login_mfa:
        result_mfa_challenge = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-password",
            },
        )
        mock_login_mfa.assert_awaited_once()

    # 5. Handle the happy path for the MFA flow
    assert result_mfa_challenge["type"] is FlowResultType.FORM
    assert result_mfa_challenge["step_id"] == "mfa_options"
    mock_mfa_handler.async_get_mfa_options.assert_awaited_once()

    result_mfa_code = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_method": "Phone"}
    )
    mock_mfa_handler.async_select_mfa_option.assert_awaited_once_with("Phone")
    assert result_mfa_code["type"] is FlowResultType.FORM
    assert result_mfa_code["step_id"] == "mfa_code"

    result_final = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mfa_code": "good-code"}
    )
    mock_mfa_handler.async_submit_mfa_code.assert_awaited_once_with("good-code")

    # 6. Verify the reauth completes successfully
    assert result_final["type"] is FlowResultType.ABORT
    assert result_final["reason"] == "reauth_successful"
    await hass.async_block_till_done()

    # Check that data was updated and the entry was reloaded
    assert mock_config_entry.data["password"] == "new-password"
    assert mock_config_entry.data["login_data"] == {
        "login_data_mock_key": "login_data_mock_value"
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
