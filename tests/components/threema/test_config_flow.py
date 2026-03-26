"""Test the Threema Gateway config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from threema.gateway import GatewayError

from homeassistant import config_entries
from homeassistant.components.threema.client import ThreemaAuthError
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
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_API_SECRET, MOCK_GATEWAY_ID, MOCK_PRIVATE_KEY

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry():
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Choose existing gateway
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"setup_type": "add_gateway"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    # Enter credentials
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


async def test_user_flow_existing_with_keys(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test user flow with existing gateway including optional keys."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"setup_type": "add_gateway"},
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


async def test_user_flow_new_gateway(
    hass: HomeAssistant, mock_connection: MagicMock
) -> None:
    """Test user flow with new gateway (key generation)."""
    mock_private = "private:generated_private_key_hex"
    mock_public = "public:generated_public_key_hex"

    with patch(
        "homeassistant.components.threema.config_flow.generate_key_pair",
        return_value=(mock_private, mock_public),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Choose new gateway
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"setup_type": "generate_keys"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "setup_new"

        # Confirm keys and proceed
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "public_key": mock_public,
                "private_key": mock_private,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "credentials"

        # Enter gateway credentials
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
                CONF_API_SECRET: MOCK_API_SECRET,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRIVATE_KEY] == mock_private
    assert result["data"][CONF_PUBLIC_KEY] == mock_public


async def test_user_flow_key_generation_failure(hass: HomeAssistant) -> None:
    """Test user flow aborts when key generation fails."""
    with patch(
        "homeassistant.components.threema.config_flow.generate_key_pair",
        side_effect=RuntimeError("Key generation failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"setup_type": "generate_keys"},
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"setup_type": "add_gateway"},
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"setup_type": "add_gateway"},
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


async def test_credentials_cannot_connect(hass: HomeAssistant) -> None:
    """Test credentials step when connection fails."""
    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(
            side_effect=GatewayError("Connection refused")
        )
        connection_class.return_value = connection

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"setup_type": "add_gateway"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
                CONF_API_SECRET: MOCK_API_SECRET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_credentials_invalid_auth(hass: HomeAssistant) -> None:
    """Test credentials step with invalid authentication."""
    with patch(
        "homeassistant.components.threema.config_flow.ThreemaAPIClient.validate_credentials",
        side_effect=ThreemaAuthError("Invalid credentials"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"setup_type": "add_gateway"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_GATEWAY_ID: MOCK_GATEWAY_ID,
                CONF_API_SECRET: MOCK_API_SECRET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.config_flow.ThreemaAPIClient.validate_credentials",
        side_effect=ThreemaAuthError("Invalid credentials"),
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_SECRET: "wrong_secret",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test reauth flow succeeds with valid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_SECRET: "new_secret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_SECRET] == "new_secret"


async def test_reauth_flow_preserves_private_key(
    hass: HomeAssistant,
    mock_config_entry_with_keys: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test reauth flow preserves existing private key when not provided."""
    mock_config_entry_with_keys.add_to_hass(hass)

    result = await mock_config_entry_with_keys.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_SECRET: "new_secret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry_with_keys.data[CONF_API_SECRET] == "new_secret"
    assert mock_config_entry_with_keys.data[CONF_PRIVATE_KEY] == MOCK_PRIVATE_KEY


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with connection failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.threema.client.Connection", autospec=True
    ) as connection_class:
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=connection)
        connection.__aexit__ = AsyncMock(return_value=None)
        connection.get_credits = AsyncMock(
            side_effect=GatewayError("Connection refused")
        )
        connection_class.return_value = connection

        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_SECRET: "new_secret",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_subentry_add_recipient(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
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


async def test_subentry_invalid_recipient_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test subentry flow rejects invalid Threema ID."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    # Too short
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "ABC"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_recipient_id"}

    # Special characters
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "ABCD!@#$"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_recipient_id"}


async def test_subentry_duplicate_recipient(
    hass: HomeAssistant,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_send: MagicMock,
) -> None:
    """Test subentry flow rejects duplicate recipient."""
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_subentry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_RECIPIENT: "ABCD1234"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
