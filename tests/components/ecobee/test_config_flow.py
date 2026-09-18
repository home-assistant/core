"""Tests for the ecobee config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyecobee import (
    ECOBEE_PASSWORD,
    ECOBEE_USERNAME,
    EcobeeAuthFailedError,
    EcobeeAuthMfaRequiredError,
    EcobeeAuthUnknownError,
    MfaChallenge,
)
import pytest

from homeassistant.components.ecobee.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _mfa_challenge() -> MfaChallenge:
    """Return a minimal MfaChallenge payload for tests."""
    return MfaChallenge(
        challenge_url="https://auth.ecobee.com/u/mfa-otp-challenge?state=abc",
        state="abc",
        mfa_type="otp",
        cookies={},
        code_verifier="verifier",
    )


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the actual integration from being set up."""
    with patch(
        "homeassistant.components.ecobee.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if ecobee is already setup."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_step_without_user_input(hass: HomeAssistant) -> None:
    """Test expected result if user step is called."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_pin_request_succeeds(hass: HomeAssistant) -> None:
    """Test expected result if pin request succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.request_pin.return_value = True
        mock_ecobee.pin = "test-pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "api-key"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"
    assert result["description_placeholders"] == {
        "pin": "test-pin",
        "auth_url": "https://www.ecobee.com/consumerportal/index.html",
    }


async def test_pin_request_fails(hass: HomeAssistant) -> None:
    """Test expected result if pin request fails, then recovers on retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee.return_value.request_pin.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "api-key"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "pin_request_failed"

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.request_pin.return_value = True
        flow_instance.pin = "test-pin"
        flow_instance.request_tokens.return_value = True
        flow_instance.api_key = "test-api-key"
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "api-key"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFRESH_TOKEN: "test-token",
    }


async def test_token_request_succeeds(hass: HomeAssistant) -> None:
    """Test expected result if token request succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.request_pin.return_value = True
        flow_instance.pin = "test-pin"
        flow_instance.request_tokens.return_value = True
        flow_instance.api_key = "test-api-key"
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "api-key"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFRESH_TOKEN: "test-token",
    }


async def test_token_request_fails(hass: HomeAssistant) -> None:
    """Test expected result if token request fails, then recovers on retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.request_pin.return_value = True
        flow_instance.pin = "test-pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "api-key"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        flow_instance.request_tokens.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert result["errors"]["base"] == "token_request_failed"
        assert result["description_placeholders"] == {
            "pin": "test-pin",
            "auth_url": "https://www.ecobee.com/consumerportal/index.html",
        }

        flow_instance.request_tokens.return_value = True
        flow_instance.api_key = "test-api-key"
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFRESH_TOKEN: "test-token",
    }


async def test_password_login_succeeds(hass: HomeAssistant) -> None:
    """Test credential authentication succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token",
    }
    mock_flow_ecobee.assert_called_once_with(
        config={
            ECOBEE_USERNAME: "test-username@example.com",
            ECOBEE_PASSWORD: "test-password",
        }
    )
    flow_instance.refresh_tokens.assert_called_once_with()


@pytest.mark.parametrize(
    ("first_user_input", "expected_error"),
    [
        (
            {
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
            "login_failed",
        ),
        (
            {
                CONF_API_KEY: "test-api-key",
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
            "invalid_auth",
        ),
    ],
)
async def test_password_login_error_recovers(
    hass: HomeAssistant,
    first_user_input: dict,
    expected_error: str,
) -> None:
    """Test auth errors keep the user on the form and recover on retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        mock_flow_ecobee.return_value.refresh_tokens.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=first_user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == expected_error

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token",
    }


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (EcobeeAuthFailedError("bad creds"), "invalid_auth"),
        (EcobeeAuthUnknownError("network down"), "unknown"),
    ],
)
async def test_password_login_raises_auth_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test that pyecobee auth exceptions map to user-facing form errors, then recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        mock_flow_ecobee.return_value.refresh_tokens.side_effect = exception

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == expected_error

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "test-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token",
    }


async def test_password_login_with_mfa_challenge_succeeds(hass: HomeAssistant) -> None:
    """Test the MFA branch: password POST triggers MFA, code completes login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    challenge = _mfa_challenge()
    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError(challenge)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["description_placeholders"] == {"mfa_type": "otp"}

        flow_instance.submit_mfa_code.return_value = True
        flow_instance.refresh_token = "test-token-after-mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token-after-mfa",
    }
    flow_instance.submit_mfa_code.assert_called_once_with(challenge, "123456")


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (EcobeeAuthFailedError("wrong code"), "invalid_mfa_code"),
        (EcobeeAuthUnknownError("auth0 hiccup"), "unknown"),
    ],
)
async def test_mfa_submission_errors_recover(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test that errors during MFA submission keep the user on the form and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError(
            _mfa_challenge()
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        assert result["step_id"] == "mfa"

        flow_instance.submit_mfa_code.side_effect = exception

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "999999"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == expected_error

        flow_instance.submit_mfa_code.side_effect = None
        flow_instance.submit_mfa_code.return_value = True
        flow_instance.refresh_token = "test-token-after-recovery"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token-after-recovery",
    }


@pytest.mark.parametrize("blank_code", ["", "   ", "\t\n "])
async def test_mfa_submission_rejects_blank_code(
    hass: HomeAssistant, blank_code: str
) -> None:
    """Whitespace-only MFA code is rejected client-side, flow then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError(
            _mfa_challenge()
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        assert result["step_id"] == "mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": blank_code}
        )

        flow_instance.submit_mfa_code.assert_not_called()
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_mfa_code"

        flow_instance.submit_mfa_code.return_value = True
        flow_instance.refresh_token = "test-token-after-recovery"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token-after-recovery",
    }


async def test_reauth_flow_succeeds(hass: HomeAssistant) -> None:
    """Test the reauth flow updates the existing entry with a fresh refresh_token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username@example.com",
            CONF_PASSWORD: "stale-password",
            CONF_REFRESH_TOKEN: "stale-refresh-token",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == "test-username@example.com"

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "fresh-refresh-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "new-password",
        CONF_REFRESH_TOKEN: "fresh-refresh-token",
    }


async def test_reauth_flow_with_mfa_challenge(hass: HomeAssistant) -> None:
    """Test that reauth surfacing MFA routes through the same mfa step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username@example.com",
            CONF_PASSWORD: "stale-password",
            CONF_REFRESH_TOKEN: "stale-refresh-token",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    challenge = _mfa_challenge()
    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError(challenge)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
        )

        assert result["step_id"] == "mfa"

        flow_instance.submit_mfa_code.return_value = True
        flow_instance.refresh_token = "reauth-refresh-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_REFRESH_TOKEN] == "reauth-refresh-token"
    assert entry.data[CONF_PASSWORD] == "new-password"
    flow_instance.submit_mfa_code.assert_called_once_with(challenge, "123456")


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (EcobeeAuthFailedError("bad creds"), "invalid_auth"),
        (EcobeeAuthUnknownError("network down"), "unknown"),
    ],
)
async def test_reauth_flow_error_branches(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Auth errors during reauth keep the user on the reauth form, then recover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username@example.com",
            CONF_PASSWORD: "stale-password",
            CONF_REFRESH_TOKEN: "stale-refresh-token",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        mock_flow_ecobee.return_value.refresh_tokens.side_effect = exception

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == expected_error

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "fresh-refresh-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "new-password",
        CONF_REFRESH_TOKEN: "fresh-refresh-token",
    }


async def test_mfa_step_submit_returns_false(hass: HomeAssistant) -> None:
    """submit_mfa_code returning False surfaces invalid_mfa_code, then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError(
            _mfa_challenge()
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test-username@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        assert result["step_id"] == "mfa"

        flow_instance.submit_mfa_code.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "999999"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"]["base"] == "invalid_mfa_code"

        flow_instance.submit_mfa_code.return_value = True
        flow_instance.refresh_token = "test-token-after-recovery"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "test-username@example.com",
        CONF_PASSWORD: "test-password",
        CONF_REFRESH_TOKEN: "test-token-after-recovery",
    }


async def test_reauth_returns_false_surfaces_login_failed(hass: HomeAssistant) -> None:
    """refresh_tokens returning False during reauth surfaces login_failed, then recovers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username@example.com",
            CONF_PASSWORD: "stale-password",
            CONF_REFRESH_TOKEN: "stale-refresh-token",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        mock_flow_ecobee.return_value.refresh_tokens.return_value = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "login_failed"

    with patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_flow_ecobee:
        flow_instance = mock_flow_ecobee.return_value
        flow_instance.refresh_tokens.return_value = True
        flow_instance.refresh_token = "fresh-refresh-token"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_REFRESH_TOKEN] == "fresh-refresh-token"
    assert entry.data[CONF_PASSWORD] == "new-password"
