"""Tests for the Mastodon config flow."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonError
import pytest

from homeassistant.components.mastodon.const import CONF_BASE_URL, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
            CONF_NAME: "Mastodon",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mastodon"
    assert result["data"] == {
        CONF_BASE_URL: "https://mastodon.social",
        CONF_CLIENT_ID: "client_id",
        CONF_CLIENT_SECRET: "client_secret",
        CONF_ACCESS_TOKEN: "access_token",
        CONF_NAME: "Mastodon",
    }
    assert result["result"].unique_id == "client_id"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MastodonError, "credential_error"),
        (Exception, "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_mastodon_client.account_verify_credentials.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
            CONF_NAME: "Mastodon",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_mastodon_client.account_verify_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
            CONF_NAME: "Mastodon",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
            CONF_NAME: "Mastodon",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test importing yaml config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "import_client_id",
            CONF_CLIENT_SECRET: "import_client_secret",
            CONF_ACCESS_TOKEN: "import_access_token",
            CONF_NAME: "Mastodon Import",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MastodonError, "credential_error"),
        (Exception, "unknown"),
    ],
)
async def test_import_flow_abort(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test importing yaml config abort."""
    mock_mastodon_client.account_verify_credentials.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "import_client_id",
            CONF_CLIENT_SECRET: "import_client_secret",
            CONF_ACCESS_TOKEN: "import_access_token",
            CONF_NAME: "Mastodon Import",
        },
    )
    assert result["type"] is FlowResultType.ABORT


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_CLIENT_ID] == "client_id"
    assert mock_config_entry.data[CONF_CLIENT_SECRET] == "client_secret2"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "access_token2"


async def test_reauth_flow_wrong_client_id(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with wrong account."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CLIENT_ID: "WRONG_CLIENT_ID",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_client_id"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MastodonError, "credential_error"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauth flow errors."""
    await setup_integration(hass, mock_config_entry)
    mock_mastodon_client.account_verify_credentials.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_mastodon_client.account_verify_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id2",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
            CONF_NAME: "Mastodon",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_BASE_URL] == "https://mastodon.social"
    assert mock_config_entry.data[CONF_CLIENT_ID] == "client_id2"
    assert mock_config_entry.data[CONF_CLIENT_SECRET] == "client_secret2"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "access_token2"
    assert mock_config_entry.data[CONF_NAME] == "Mastodon"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (MastodonError, "credential_error"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_flow_exceptions(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reconfigure flow errors."""
    await setup_integration(hass, mock_config_entry)
    mock_mastodon_client.account_verify_credentials.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id2",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
            CONF_NAME: "Mastodon",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"
    assert result["errors"] == {"base": error}

    mock_mastodon_client.account_verify_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id2",
            CONF_CLIENT_SECRET: "client_secret2",
            CONF_ACCESS_TOKEN: "access_token2",
            CONF_NAME: "Mastodon",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
