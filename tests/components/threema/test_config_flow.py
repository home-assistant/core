"""Test the Threema Gateway config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.threema.client import (
    ThreemaAuthError,
    ThreemaConnectionError,
)
from homeassistant.components.threema.const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    CONF_PUBLIC_KEY,
    CONF_RECIPIENT,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

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
    """Test user flow with existing gateway including optional keys."""
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
            CONF_PUBLIC_KEY: "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_PRIVATE_KEY]
        == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    assert (
        result["data"][CONF_PUBLIC_KEY]
        == "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    )
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_new_gateway(
    hass: HomeAssistant, mock_credentials: AsyncMock
) -> None:
    """Test user flow with new gateway (key generation)."""
    with patch(
        "homeassistant.components.threema.config_flow.generate_key_pair",
        return_value=("generated_private_hex", "generated_public_hex"),
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
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == "generated_private_hex"
    assert result["data"][CONF_PUBLIC_KEY] == "generated_public_hex"
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
    assert result["data"] == {CONF_RECIPIENT: "EFGH5678"}
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
    """Test subentry flow rejects invalid Threema ID via schema validation."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_RECIPIENT: invalid_id},
        )


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
