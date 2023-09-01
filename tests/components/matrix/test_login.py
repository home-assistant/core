"""Test MatrixBot._login."""
from enum import Enum, auto

from pydantic.dataclasses import dataclass
import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from tests.components.matrix.conftest import (
    TEST_DEVICE_ID,
    TEST_MXID,
    TEST_PASSWORD,
    TEST_TOKEN,
)


class ParameterStatus(Enum):
    """Whether a given parameter is good, bad, or not provided."""

    good = auto()
    bad = auto()
    missing = auto()


@dataclass
class LoginTestParameters:
    """Dataclass of parameters representing the login parameters and expected result state."""

    password: ParameterStatus
    access_token: ParameterStatus
    expected_login_state: bool
    expected_caplog_messages: set[str]
    expected_expection: type(Exception) | None = None


good_password_missing_token = LoginTestParameters(
    password=ParameterStatus.good,
    access_token=ParameterStatus.missing,
    expected_login_state=True,
    expected_caplog_messages={"Logging in using password"},
)

good_password_bad_token = LoginTestParameters(
    password=ParameterStatus.good,
    access_token=ParameterStatus.bad,
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from stored access token",
        "Restoring login from access token failed: M_UNKNOWN_TOKEN, Invalid access token passed.",
        "Logging in using password",
    },
)

bad_password_good_access_token = LoginTestParameters(
    password=ParameterStatus.bad,
    access_token=ParameterStatus.good,
    expected_login_state=True,
    expected_caplog_messages={
        "Restoring login from stored access token",
        f"Successfully restored login from access token: user_id '{TEST_MXID}', device_id '{TEST_DEVICE_ID}'",
    },
)

bad_password_bad_access_token = LoginTestParameters(
    password=ParameterStatus.bad,
    access_token=ParameterStatus.bad,
    expected_login_state=False,
    expected_caplog_messages={
        "Restoring login from stored access token",
        "Restoring login from access token failed: M_UNKNOWN_TOKEN, Invalid access token passed.",
        "Logging in using password",
        "Login by password failed: status_code, LoginError",
    },
    expected_expection=ConfigEntryAuthFailed,
)

bad_password_missing_access_token = LoginTestParameters(
    password=ParameterStatus.bad,
    access_token=ParameterStatus.missing,
    expected_login_state=False,
    expected_caplog_messages={
        "Logging in using password",
        "Login by password failed: status_code, LoginError",
    },
    expected_expection=ConfigEntryAuthFailed,
)


@pytest.mark.parametrize(
    "params",
    [
        good_password_missing_token,
        good_password_bad_token,
        bad_password_good_access_token,
        bad_password_bad_access_token,
        bad_password_missing_access_token,
    ],
)
async def test_login(
    matrix_bot: MatrixBot, caplog: pytest.LogCaptureFixture, params: LoginTestParameters
):
    """Test logging in with the given parameters and expected state."""
    await matrix_bot._client.logout()
    matrix_bot._password = (
        TEST_PASSWORD if params.password is ParameterStatus.good else "WrongPassword"
    )
    match params.access_token:
        case ParameterStatus.good:
            matrix_bot._access_tokens = {TEST_MXID: TEST_TOKEN}
        case ParameterStatus.bad:
            matrix_bot._access_tokens = {TEST_MXID: "WrongToken"}
        case ParameterStatus.missing:
            matrix_bot._access_tokens = {}

    if params.expected_expection is not None:
        with pytest.raises(params.expected_expection):
            await matrix_bot._login()
    else:
        await matrix_bot._login()
    assert matrix_bot._client.logged_in == params.expected_login_state
    assert set(caplog.messages).issuperset(params.expected_caplog_messages)


async def test_get_auth_tokens(matrix_bot: MatrixBot, mock_load_json):
    """Test loading access_tokens from a mocked file."""

    # Test loading good tokens.
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {TEST_MXID: TEST_TOKEN}

    # Test miscellaneous error from hass.
    mock_load_json.side_effect = HomeAssistantError()
    loaded_tokens = await matrix_bot._get_auth_tokens()
    assert loaded_tokens == {}
