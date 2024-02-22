"""Test the August config flow."""
from unittest.mock import patch

from yalexs.authenticator import ValidationResult

from homeassistant import config_entries
from homeassistant.components.august.const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_BRAND,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DOMAIN,
    VERIFICATION_CODE_KEY,
)
from homeassistant.components.august.exceptions import (
    CannotConnect,
    InvalidAuth,
    RequireValidation,
)
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.august.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "august",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "my@email.tld"
    assert result2["data"] == {
        CONF_BRAND: "august",
        CONF_LOGIN_METHOD: "email",
        CONF_USERNAME: "my@email.tld",
        CONF_INSTALL_ID: None,
        CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "august",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=ValueError("something exploded"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "august",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unhandled"}
    assert result2["description_placeholders"] == {"error": "something exploded"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_needs_validate(hass: HomeAssistant) -> None:
    """Test we present validation when we need to validate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=RequireValidation,
    ), patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_send_verification_code",
        return_value=True,
    ) as mock_send_verification_code:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )

    assert len(mock_send_verification_code.mock_calls) == 1
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "validation"

    # Try with the WRONG verification code give us the form back again
    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=RequireValidation,
    ), patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_validate_verification_code",
        return_value=ValidationResult.INVALID_VERIFICATION_CODE,
    ) as mock_validate_verification_code, patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_send_verification_code",
        return_value=True,
    ) as mock_send_verification_code:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {VERIFICATION_CODE_KEY: "incorrect"},
        )

    # Make sure we do not resend the code again
    # so they have a chance to retry
    assert len(mock_send_verification_code.mock_calls) == 0
    assert len(mock_validate_verification_code.mock_calls) == 1
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_verification_code"}
    assert result3["step_id"] == "validation"

    # Try with the CORRECT verification code and we setup
    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_validate_verification_code",
        return_value=ValidationResult.VALIDATED,
    ) as mock_validate_verification_code, patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_send_verification_code",
        return_value=True,
    ) as mock_send_verification_code, patch(
        "homeassistant.components.august.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {VERIFICATION_CODE_KEY: "correct"},
        )
        await hass.async_block_till_done()

    assert len(mock_send_verification_code.mock_calls) == 0
    assert len(mock_validate_verification_code.mock_calls) == 1
    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "my@email.tld"
    assert result4["data"] == {
        CONF_BRAND: "august",
        CONF_LOGIN_METHOD: "email",
        CONF_USERNAME: "my@email.tld",
        CONF_INSTALL_ID: None,
        CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test reauthenticate."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOGIN_METHOD: "email",
            CONF_USERNAME: "my@email.tld",
            CONF_PASSWORD: "test-password",
            CONF_INSTALL_ID: None,
            CONF_TIMEOUT: 10,
            CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
        },
        unique_id="my@email.tld",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=entry.data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.august.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reauth_with_2fa(hass: HomeAssistant) -> None:
    """Test reauthenticate with 2fa."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOGIN_METHOD: "email",
            CONF_USERNAME: "my@email.tld",
            CONF_PASSWORD: "test-password",
            CONF_INSTALL_ID: None,
            CONF_TIMEOUT: 10,
            CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
        },
        unique_id="my@email.tld",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data=entry.data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        side_effect=RequireValidation,
    ), patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_send_verification_code",
        return_value=True,
    ) as mock_send_verification_code:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert len(mock_send_verification_code.mock_calls) == 1
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] is None
    assert result2["step_id"] == "validation"

    # Try with the CORRECT verification code and we setup
    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_validate_verification_code",
        return_value=ValidationResult.VALIDATED,
    ) as mock_validate_verification_code, patch(
        "homeassistant.components.august.gateway.AuthenticatorAsync.async_send_verification_code",
        return_value=True,
    ) as mock_send_verification_code, patch(
        "homeassistant.components.august.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {VERIFICATION_CODE_KEY: "correct"},
        )
        await hass.async_block_till_done()

    assert len(mock_validate_verification_code.mock_calls) == 1
    assert len(mock_send_verification_code.mock_calls) == 0
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_switching_brands(hass: HomeAssistant) -> None:
    """Test brands can be switched by setting up again."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOGIN_METHOD: "email",
            CONF_USERNAME: "my@email.tld",
            CONF_PASSWORD: "test-password",
            CONF_INSTALL_ID: None,
            CONF_TIMEOUT: 10,
            CONF_ACCESS_TOKEN_CACHE_FILE: ".my@email.tld.august.conf",
        },
        unique_id="my@email.tld",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.august.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: "yale_home",
                CONF_LOGIN_METHOD: "email",
                CONF_USERNAME: "my@email.tld",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.data[CONF_BRAND] == "yale_home"
