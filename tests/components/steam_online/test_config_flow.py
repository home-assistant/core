"""Test Steam config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import steam.api

from homeassistant.components.steam_online.const import CONF_ACCOUNTS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from . import (
    ACCOUNT_1,
    ACCOUNT_2,
    ACCOUNT_NAME_1,
    CONF_DATA,
    CONF_OPTIONS,
    CONF_OPTIONS_2,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("steam_api")
async def test_flow_user(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user initialized flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NAME_1
    assert result["data"] == CONF_DATA
    assert result["options"] == CONF_OPTIONS
    assert result["result"].unique_id == ACCOUNT_1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        (steam.api.HTTPTimeoutError, "timeout_connect"),
        (steam.api.HTTPError, "cannot_connect"),
        (steam.api.HTTPError("403"), "invalid_auth"),
        (ValueError, "unknown"),
        ([{"response": {"players": {"player": [None]}}}], "invalid_account"),
    ],
)
async def test_flow_user_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception] | dict[str, Any],
    error_msg: str,
    steam_api: MagicMock,
) -> None:
    """Test user initialized flow with errors."""

    steam_api.return_value.GetPlayerSummaries.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    steam_api.return_value.GetPlayerSummaries.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NAME_1
    assert result["data"] == CONF_DATA
    assert result["options"] == CONF_OPTIONS
    assert result["result"].unique_id == ACCOUNT_1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("steam_api")
async def test_flow_user_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test user initialized flow with duplicate account."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("steam_api")
async def test_flow_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth step."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {**CONF_DATA, CONF_API_KEY: "1234567890"}

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        (steam.api.HTTPTimeoutError, "timeout_connect"),
        (steam.api.HTTPError, "cannot_connect"),
        (steam.api.HTTPError("403"), "invalid_auth"),
        (ValueError, "unknown"),
        ([{"response": {"players": {"player": [None]}}}], "invalid_account"),
    ],
)
async def test_flow_reauth_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
    side_effect: type[Exception] | dict[str, Any],
    error_msg: str,
) -> None:
    """Test reauth step with errors."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    steam_api.return_value.GetPlayerSummaries.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    steam_api.return_value.GetPlayerSummaries.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {**CONF_DATA, CONF_API_KEY: "1234567890"}

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("steam_api")
async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test updating options."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNTS: [ACCOUNT_1, ACCOUNT_2]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS_2


@pytest.mark.usefixtures("steam_api")
async def test_options_flow_deselect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test deselecting user."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNTS: []},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCOUNTS: {}}
    assert len(entity_registry.entities) == 0


async def test_options_flow_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
) -> None:
    """Test updating options timeout getting friends list."""
    config_entry.add_to_hass(hass)

    steam_api.return_value.GetFriendList.side_effect = steam.api.HTTPTimeoutError
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNTS: [ACCOUNT_1]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS


async def test_options_flow_unauthorized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
) -> None:
    """Test updating options when user's friends list is not public."""
    config_entry.add_to_hass(hass)
    steam_api.return_value.GetFriendList.side_effect = steam.api.HTTPError
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNTS: [ACCOUNT_1]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_OPTIONS


@pytest.mark.usefixtures("steam_api")
async def test_flow_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure step."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {**CONF_DATA, CONF_API_KEY: "1234567890"}

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        (steam.api.HTTPError, "cannot_connect"),
        (steam.api.HTTPError("403"), "invalid_auth"),
        (ValueError, "unknown"),
        ([{"response": {"players": {"player": [None]}}}], "invalid_account"),
    ],
)
async def test_flow_reconfigure_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
    side_effect: Exception | dict[str, Any],
    error_msg: str,
) -> None:
    """Test reconfigure step with errors."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    steam_api.return_value.GetPlayerSummaries.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    steam_api.return_value.GetPlayerSummaries.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "1234567890"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {**CONF_DATA, CONF_API_KEY: "1234567890"}

    assert len(hass.config_entries.async_entries()) == 1
