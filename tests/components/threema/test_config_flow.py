"""Test the Threema Gateway config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from threema.gateway import GatewayError
from threema.gateway.exception import GatewayServerError

from homeassistant import config_entries
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

from .conftest import MOCK_API_SECRET, MOCK_GATEWAY_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Patch async_setup_entry to avoid full setup during flow tests."""
    with patch("homeassistant.components.threema.async_setup_entry", return_value=True):
        yield


async def test_user_flow_existing_gateway(
    hass: HomeAssistant, mock_connection: MagicMock
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Threema {MOCK_GATEWAY_ID}"
    assert result["data"] == {
        CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
        CONF_API_SECRET: MOCK_API_SECRET,
    }
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_existing_with_keys(
    hass: HomeAssistant, mock_connection: MagicMock
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
            CONF_PRIVATE_KEY: "private:abcdef1234567890",
            CONF_PUBLIC_KEY: "public:1234567890abcdef",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == "private:abcdef1234567890"
    assert result["data"][CONF_PUBLIC_KEY] == "public:1234567890abcdef"
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_new_gateway(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test user flow with new gateway (key generation)."""
    mock_private_key = MagicMock()
    mock_public_key = MagicMock()

    with (
        patch(
            "homeassistant.components.threema.client.key.Key.generate_pair",
            return_value=(mock_private_key, mock_public_key),
        ),
        patch(
            "homeassistant.components.threema.client.key.Key.encode",
            side_effect=[
                "private:generated_private_key_hex",
                "public:generated_public_key_hex",
            ],
        ),
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
            user_input={
                "public_key": "public:generated_public_key_hex",
                "private_key": "private:generated_private_key_hex",
            },
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
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == "private:generated_private_key_hex"
    assert result["data"][CONF_PUBLIC_KEY] == "public:generated_public_key_hex"
    assert result["result"].unique_id == MOCK_GATEWAY_ID


async def test_user_flow_key_generation_failure(hass: HomeAssistant) -> None:
    """Test user flow aborts when key generation fails."""
    with patch(
        "homeassistant.components.threema.client.key.Key.generate_pair",
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
    hass: HomeAssistant, mock_connection: MagicMock
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
    mock_connection: MagicMock,
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
        (GatewayError("Connection refused"), "cannot_connect"),
        (GatewayServerError(status=500), "cannot_connect"),
        (GatewayServerError(status=401), "invalid_auth"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
    ids=["cannot_connect", "server_error_non_auth", "invalid_auth", "unknown_error"],
)
async def test_credentials_error(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test credentials step with various errors."""
    mock_connection.get_credits.side_effect = side_effect

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


async def test_subentry_add_recipient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
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
        user_input={CONF_RECIPIENT: "ABCD1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABCD1234"
    assert result["data"] == {CONF_RECIPIENT: "ABCD1234"}
    assert result["unique_id"] == "ABCD1234"


async def test_subentry_add_recipient_with_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
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
        user_input={CONF_RECIPIENT: "ABCD1234", "name": "Dad"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dad (ABCD1234)"
    assert result["data"] == {CONF_RECIPIENT: "ABCD1234"}
    assert result["unique_id"] == "ABCD1234"


@pytest.mark.parametrize(
    "invalid_id",
    ["ABC", "ABCD!@#$", ""],
    ids=["too_short", "special_chars", "empty"],
)
async def test_subentry_invalid_recipient_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
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
    mock_connection: MagicMock,
    mock_send: tuple[MagicMock, MagicMock],
) -> None:
    """Test subentry flow rejects duplicate recipient."""
    entry = MockConfigEntry(
        title=f"Threema {MOCK_GATEWAY_ID}",
        domain=DOMAIN,
        data={
            CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
            CONF_API_SECRET: MOCK_API_SECRET,
        },
        unique_id=MOCK_GATEWAY_ID,
        subentries_data=[
            {
                "data": {CONF_RECIPIENT: "ABCD1234"},
                "subentry_id": "mock_subentry_id",
                "subentry_type": SUBENTRY_TYPE_RECIPIENT,
                "title": "ABCD1234",
                "unique_id": "ABCD1234",
            },
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "ABCD1234"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
