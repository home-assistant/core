"""Test MatrixBot._login."""

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .conftest import TEST_DEVICE_ID, TEST_MXID, TEST_PASSWORD, TEST_TOKEN


@dataclass
class LoginTestParameters:
    """Login parameters and expected result state."""

    password: str | None
    access_token: dict[str, str]
    expected_login_state: bool
    expected_caplog_messages: set[str]
    expected_expection: type[Exception] | None = None
    configured_access_token: str | None = None
    unexpected_caplog_messages: set[str] = field(default_factory=set)
    expected_token_stored: bool = True


good_password_missing_token = LoginTestParameters(
    password=TEST_PASSWORD,
    access_token={},
    expected_login_state=True,
    expected_caplog_messages={"Logging in using password"},
)

good_password_bad_token = LoginTestParameters(
    password=TEST_PASSWORD,
    access_token={TEST_MXID: "WrongToken"},
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from stored access token",
        "Restoring login from access token failed:"
        " M_UNKNOWN_TOKEN, Invalid access token passed.",
        "Logging in using password",
    },
)

bad_password_good_access_token = LoginTestParameters(
    password="WrongPassword",
    access_token={TEST_MXID: TEST_TOKEN},
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from stored access token",
        "Successfully restored login from access token:"
        f" user_id '{TEST_MXID}', device_id '{TEST_DEVICE_ID}'",
    },
)

bad_password_bad_access_token = LoginTestParameters(
    password="WrongPassword",
    access_token={TEST_MXID: "WrongToken"},
    expected_login_state=False,
    expected_caplog_messages={
        "Restoring login from stored access token",
        "Restoring login from access token failed:"
        " M_UNKNOWN_TOKEN, Invalid access token passed.",
        "Logging in using password",
        "Login by password failed: status_code, LoginError",
    },
    expected_expection=ConfigEntryAuthFailed,
    expected_token_stored=False,
)

bad_password_missing_access_token = LoginTestParameters(
    password="WrongPassword",
    access_token={},
    expected_login_state=False,
    expected_caplog_messages={
        "Logging in using password",
        "Login by password failed: status_code, LoginError",
    },
    expected_expection=ConfigEntryAuthFailed,
    expected_token_stored=False,
)

configured_token_no_password = LoginTestParameters(
    password=None,
    configured_access_token=TEST_TOKEN,
    access_token={},
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from configured access token",
        "Successfully restored login from access token:"
        f" user_id '{TEST_MXID}', device_id '{TEST_DEVICE_ID}'",
    },
    unexpected_caplog_messages={"Logging in using password"},
    expected_token_stored=False,
)

configured_token_overrides_stored_token = LoginTestParameters(
    password=None,
    configured_access_token=TEST_TOKEN,
    access_token={TEST_MXID: "WrongToken"},
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from configured access token",
        "Successfully restored login from access token:"
        f" user_id '{TEST_MXID}', device_id '{TEST_DEVICE_ID}'",
    },
    unexpected_caplog_messages={"Restoring login from stored access token"},
    expected_token_stored=False,
)

bad_configured_token_no_password = LoginTestParameters(
    password=None,
    configured_access_token="WrongToken",
    access_token={},
    expected_login_state=False,
    expected_caplog_messages={
        "Restoring login from configured access token",
        "Restoring login from access token failed:"
        " M_UNKNOWN_TOKEN, Invalid access token passed.",
    },
    unexpected_caplog_messages={"Logging in using password"},
    expected_expection=ConfigEntryAuthFailed,
    expected_token_stored=False,
)


@pytest.mark.parametrize(
    "params",
    [
        good_password_missing_token,
        good_password_bad_token,
        bad_password_good_access_token,
        bad_password_bad_access_token,
        bad_password_missing_access_token,
        configured_token_no_password,
        configured_token_overrides_stored_token,
        bad_configured_token_no_password,
    ],
)
async def test_login(
    matrix_bot: MatrixBot,
    caplog: pytest.LogCaptureFixture,
    mock_save_json: MagicMock,
    params: LoginTestParameters,
) -> None:
    """Test logging in with the given parameters and expected state."""
    await matrix_bot._client.logout()
    matrix_bot._password = params.password
    matrix_bot._configured_access_token = params.configured_access_token
    matrix_bot._access_tokens = params.access_token
    # The matrix_bot fixture already logged in and stored a token during startup.
    mock_save_json.reset_mock()

    if params.expected_expection:
        with pytest.raises(params.expected_expection):
            await matrix_bot._login()
    else:
        await matrix_bot._login()
    assert matrix_bot._client.logged_in == params.expected_login_state
    assert set(caplog.messages).issuperset(params.expected_caplog_messages)
    assert set(caplog.messages).isdisjoint(params.unexpected_caplog_messages)
    assert mock_save_json.called == params.expected_token_stored


async def test_login_password_not_supported(
    matrix_bot: MatrixBot, mock_save_json: MagicMock
) -> None:
    """Test the error raised when the homeserver has no password login flow."""
    await matrix_bot._client.logout()
    matrix_bot._password = "WrongPassword"
    matrix_bot._access_tokens = {}
    matrix_bot._client.login_flows = ["m.login.sso", "m.login.token"]
    mock_save_json.reset_mock()

    with pytest.raises(ConfigEntryAuthFailed, match="does not offer password login"):
        await matrix_bot._login()
    mock_save_json.assert_not_called()


async def test_get_auth_tokens(matrix_bot: MatrixBot, mock_load_json) -> None:
    """Test loading access_tokens from a mocked file."""

    # Test loading good tokens.
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {TEST_MXID: TEST_TOKEN}

    # Test miscellaneous error from hass.
    mock_load_json.side_effect = HomeAssistantError()
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {}
