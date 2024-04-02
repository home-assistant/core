"""Test Lastfm config flow."""

from unittest.mock import AsyncMock

from pylast import PyLastError, WSError
import pytest

from homeassistant.components.lastfm.const import (
    CONF_MAIN_USER,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_KEY,
    CONF_DATA,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    USERNAME_1,
    setup_integration,
)

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant, mock_lastfm_network: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "friends"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_FRIENDS_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["options"] == CONF_DATA


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            WSError(
                "network",
                "status",
                "Invalid API key - You must be granted a valid key by last.fm",
            ),
            "invalid_auth",
        ),
        (WSError("network", "status", "User not found"), "invalid_account"),
        (Exception(), "unknown"),
        (WSError("network", "status", "Something strange"), "unknown"),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant,
    error: Exception,
    message: str,
    mock_lastfm_network: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_lastfm_user: AsyncMock,
) -> None:
    """Test user initialized flow with invalid username."""
    mock_lastfm_user.get_playcount.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == message

    mock_lastfm_user.get_playcount.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "friends"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_FRIENDS_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["options"] == CONF_DATA


async def test_flow_friends_invalid_username(
    hass: HomeAssistant,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user initialized flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "friends"

    mock_lastfm_user.get_playcount.side_effect = WSError(
        "network", "status", "User not found"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_FRIENDS_DATA
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "friends"
    assert result["errors"]["base"] == "invalid_account"

    mock_lastfm_user.get_playcount.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_FRIENDS_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["options"] == CONF_DATA


async def test_flow_friends_no_friends(
    hass: HomeAssistant,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test options is empty when user has no friends."""

    mock_lastfm_user.get_friends.side_effect = PyLastError(
        "network", "status", "Page not found"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_USER_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "friends"
    assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test updating options."""
    await setup_integration(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_USERS: [USERNAME_1]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
    }


async def test_options_flow_incorrect_username(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test updating options doesn't work with incorrect username."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    mock_lastfm_user.get_playcount.side_effect = WSError(
        "network", "status", "User not found"
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_USERS: [USERNAME_1]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["base"] == "invalid_account"

    mock_lastfm_user.get_playcount.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_USERS: [USERNAME_1]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
    }


async def test_options_flow_from_import(
    hass: HomeAssistant,
    imported_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test updating options gained from import."""
    await setup_integration(hass, imported_config_entry)

    mock_lastfm_user.get_friends.side_effect = PyLastError(
        "network", "status", "Page not found"
    )

    result = await hass.config_entries.options.async_init(
        imported_config_entry.entry_id
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_options_flow_without_friends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lastfm_network: AsyncMock,
    mock_lastfm_user: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test updating options for someone without friends."""
    await setup_integration(hass, mock_config_entry)
    mock_lastfm_user.get_friends.side_effect = PyLastError(
        "network", "status", "Page not found"
    )
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0
