"""Tests for the NYT Games config flow."""

from unittest.mock import AsyncMock

from nyt_games import NYTGamesAuthenticationError, NYTGamesError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nyt_games.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_nyt_games_client: AsyncMock) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NYT Games"
    assert result["data"] == {CONF_TOKEN: "token"}
    assert result["result"].unique_id == "218886794"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_stripping_token(
    hass: HomeAssistant, mock_nyt_games_client: AsyncMock
) -> None:
    """Test stripping token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: " token "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TOKEN: "token"}
    assert result["result"].unique_id == "218886794"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NYTGamesAuthenticationError, "invalid_auth"),
        (NYTGamesError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_nyt_games_client.get_user_id.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_nyt_games_client.get_user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
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
        {CONF_TOKEN: "token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: " new_token "},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_TOKEN: "new_token"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NYTGamesAuthenticationError, "invalid_auth"),
        (NYTGamesError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_nyt_games_client.get_user_id.side_effect = exception

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_nyt_games_client.get_user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_TOKEN: "new_token"}


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication with a token for a different account."""
    mock_config_entry.add_to_hass(hass)
    mock_nyt_games_client.get_user_id.return_value = 12345

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_TOKEN: "token"}


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: " new_token "},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_TOKEN: "new_token"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NYTGamesAuthenticationError, "invalid_auth"),
        (NYTGamesError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test reconfigure flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_nyt_games_client.get_user_id.side_effect = exception

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_nyt_games_client.get_user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_TOKEN: "new_token"}


async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_nyt_games_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring with a token for a different account."""
    mock_config_entry.add_to_hass(hass)
    mock_nyt_games_client.get_user_id.return_value = 12345

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "new_token"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_TOKEN: "token"}
