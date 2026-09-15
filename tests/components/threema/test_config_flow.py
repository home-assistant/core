"""Test the Threema Gateway config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.threema.client import (
    ThreemaAuthError,
    ThreemaConnectionError,
    derive_public_key,
)
from homeassistant.components.threema.config_flow import _CONF_PUBLIC_KEY
from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.const import CONF_NAME, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_API_SECRET, MOCK_GATEWAY_ID, MOCK_RECIPIENT_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Patch async_setup_entry to avoid full setup during flow tests."""
    with patch("homeassistant.components.threema.async_setup_entry", return_value=True):
        yield


async def test_user_flow_existing_gateway(
    hass: HomeAssistant, mock_credentials: AsyncMock
) -> None:
    """Test user flow with existing gateway credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Threema {MOCK_GATEWAY_ID}"
    assert result["data"] == {
        CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
        CONF_API_SECRET: MOCK_API_SECRET,
    }
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_existing_with_keys(
    hass: HomeAssistant, mock_credentials: AsyncMock
) -> None:
    """Test user flow with existing gateway including optional private key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_PRIVATE_KEY]
        == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_new_gateway(
    hass: HomeAssistant, mock_credentials: AsyncMock
) -> None:
    """Test user flow with new gateway (key generation)."""
    generated_private_key = "0" * 64
    generated_public_key = "f" * 64

    with patch(
        "homeassistant.components.threema.config_flow.generate_key_pair",
        return_value=(generated_private_key, generated_public_key),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "setup_new"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "setup_new"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
                CONF_API_SECRET: MOCK_API_SECRET,
                CONF_PRIVATE_KEY: generated_private_key,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == generated_private_key
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_key_generation_failure(hass: HomeAssistant) -> None:
    """Test user flow aborts when key generation fails."""
    with patch(
        "homeassistant.components.threema.config_flow.generate_key_pair",
        side_effect=RuntimeError("Key generation failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "setup_new"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "key_generation_failed"


async def test_credentials_invalid_gateway_id(
    hass: HomeAssistant, mock_credentials: AsyncMock
) -> None:
    """Test credentials step with invalid Gateway ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    # Gateway ID not starting with *
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: "TESTGWY1",
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_gateway_id"}

    # Gateway ID wrong length
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: "*TEST",
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_gateway_id"}

    # Right length and prefix, but invalid characters
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: "*!!!!!!!",
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_gateway_id"}

    # Valid Gateway ID — recover and create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_GATEWAY_ID


@pytest.mark.parametrize(
    "invalid_key",
    ["0123456789abcdef", "g" * 64],
    ids=["wrong_length", "non_hex"],
)
async def test_credentials_invalid_private_key(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
    invalid_key: str,
) -> None:
    """Test credentials step rejects a malformed private key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: invalid_key,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PRIVATE_KEY: "invalid_key"}

    # Recover by clearing the invalid key (the field defaults to the
    # previous, invalid value, so it must be explicitly cleared)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "prefixed_key",
    [
        "private:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "PRIVATE:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    ],
    ids=["lower", "upper"],
)
async def test_credentials_private_key_prefix_stripped(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
    prefixed_key: str,
) -> None:
    """Test a 'private:'-prefixed key (as exported by Threema's tools) is accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: prefixed_key,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_PRIVATE_KEY]
        == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )


async def test_credentials_public_key_in_private_key_field_rejected(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a 'public:'-prefixed key pasted into the private-key field is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: f"public:{'a' * 64}",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PRIVATE_KEY: "invalid_key"}


async def test_credentials_private_key_in_public_key_field_rejected(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a 'private:'-prefixed key pasted into the public-key field is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "a" * 64,
            _CONF_PUBLIC_KEY: f"private:{'b' * 64}",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {_CONF_PUBLIC_KEY: "invalid_key"}


async def test_credentials_public_key_without_private_key_rejected(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a public key given alone (no private key) is rejected, not discarded."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            _CONF_PUBLIC_KEY: "a" * 64,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {_CONF_PUBLIC_KEY: "public_key_requires_private_key"}


async def test_credentials_public_key_matches(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a public key matching the private key is accepted and not stored."""
    private_key = "1" * 64
    matching_public_key = derive_public_key(private_key)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: private_key,
            _CONF_PUBLIC_KEY: f"public:{matching_public_key}",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == private_key
    assert _CONF_PUBLIC_KEY not in result["data"]


async def test_credentials_public_key_mismatch(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a public key that does not match the private key is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "1" * 64,
            _CONF_PUBLIC_KEY: "f" * 64,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {_CONF_PUBLIC_KEY: "key_mismatch"}


async def test_credentials_public_key_invalid_hex(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test a malformed public key is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "1" * 64,
            _CONF_PUBLIC_KEY: "not-a-valid-key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {_CONF_PUBLIC_KEY: "invalid_key"}


async def test_credentials_invalid_private_key_preserves_other_fields(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
) -> None:
    """Test gateway ID and API secret stay filled in after an invalid key error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
            CONF_PRIVATE_KEY: "not-a-valid-key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PRIVATE_KEY: "invalid_key"}

    defaults = {
        schema_key: schema_key.default()
        for schema_key in result["data_schema"].schema
        if schema_key.default is not vol.UNDEFINED
    }
    assert defaults[CONF_GATEWAY_ID] == MOCK_GATEWAY_ID
    assert defaults[CONF_API_SECRET] == MOCK_API_SECRET


async def test_credentials_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
) -> None:
    """Test credentials step when gateway is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ThreemaConnectionError("Connection refused"), "cannot_connect"),
        (ThreemaConnectionError("Server error"), "cannot_connect"),
        (ThreemaAuthError("Invalid credentials"), "invalid_auth"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
    ids=["cannot_connect", "server_error_non_auth", "invalid_auth", "unknown_error"],
)
async def test_credentials_error(
    hass: HomeAssistant,
    mock_credentials: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test credentials step with various errors."""
    mock_credentials.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "credentials"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_add_recipient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test adding a recipient via subentry flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "EFGH5678"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EFGH5678"
    assert result["data"] == {CONF_RECIPIENT: "EFGH5678"}
    assert result["unique_id"] == "EFGH5678"


async def test_subentry_add_recipient_with_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test adding a recipient with a display name."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "EFGH5678", "name": "Dad"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dad (EFGH5678)"
    assert result["data"] == {CONF_RECIPIENT: "EFGH5678", CONF_NAME: "Dad"}
    assert result["unique_id"] == "EFGH5678"


@pytest.mark.parametrize(
    "invalid_id",
    ["ABC", "ABCD!@#$", ""],
    ids=["too_short", "special_chars", "empty"],
)
async def test_subentry_invalid_recipient_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
    invalid_id: str,
) -> None:
    """Test subentry flow rejects invalid Threema ID with an inline form error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: invalid_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RECIPIENT: "invalid_recipient_id"}


async def test_subentry_duplicate_recipient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    mock_send_message: AsyncMock,
) -> None:
    """Test subentry flow rejects duplicate recipient."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: MOCK_RECIPIENT_ID},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
) -> None:
    """Test reauthentication flow updates the API secret and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_SECRET: "new_api_secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_SECRET] == "new_api_secret"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ThreemaAuthError("Invalid credentials"), "invalid_auth"),
        (ThreemaConnectionError("Connection refused"), "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unknown"],
)
async def test_reauth_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication flow shows error and allows retry."""
    mock_config_entry.add_to_hass(hass)
    mock_credentials.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_SECRET: "wrong_secret"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_SECRET: "correct_secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
