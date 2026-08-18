"""Test the MELCloud Home config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_REAUTH_INPUT, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full user config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT[CONF_EMAIL]
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == "user-uuid-1"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (MelCloudHomeAuthenticationError("bad creds"), "invalid_auth"),
        (MelCloudHomeConnectionError("offline"), "cannot_connect"),
        (MelCloudHomeTimeoutError("timed out"), "timeout_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all user step exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_melcloud_client.get_context.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_melcloud_client.get_context.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT[CONF_EMAIL]
    assert result["data"] == MOCK_USER_INPUT


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow_reauth(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == MOCK_REAUTH_INPUT


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow aborts when a different account is used."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_melcloud_client.get_context.return_value = (
        mock_melcloud_client.get_context.return_value.model_copy(
            update={"id": "user-uuid-2"}
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == MOCK_USER_INPUT
    assert mock_config_entry.unique_id == "user-uuid-1"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), "invalid_auth"),
        pytest.param(MelCloudHomeConnectionError("offline"), "cannot_connect"),
        pytest.param(MelCloudHomeTimeoutError("timed out"), "timeout_connect"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions in the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_melcloud_client.get_context.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_melcloud_client.get_context.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == MOCK_REAUTH_INPUT


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == MOCK_REAUTH_INPUT


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), "invalid_auth"),
        pytest.param(MelCloudHomeConnectionError("offline"), "cannot_connect"),
        pytest.param(MelCloudHomeTimeoutError("timed out"), "timeout_connect"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
async def test_reconfigure_flow_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions in the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_melcloud_client.get_context.side_effect = MelCloudHomeConnectionError(
        "offline"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_melcloud_client.get_context.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == MOCK_REAUTH_INPUT


async def test_reconfigure_flow_wrong_account(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow aborts when a different account is used."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_melcloud_client.get_context.return_value = (
        mock_melcloud_client.get_context.return_value.model_copy(
            update={"id": "user-uuid-2"}
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == MOCK_USER_INPUT
    assert mock_config_entry.unique_id == "user-uuid-1"
