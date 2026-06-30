"""Test Steam config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import steam.api

from homeassistant.components.steam_online.const import (
    CONF_ACCOUNT,
    DOMAIN,
    SUBENTRY_TYPE_FRIEND,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ACCOUNT_1, ACCOUNT_2, ACCOUNT_NAME_1, ACCOUNT_NAME_2, API_KEY, CONF_DATA

from tests.common import MockConfigEntry, async_load_json_object_fixture


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
async def test_flow_user_already_configured_as_subentry(
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
        user_input={
            CONF_API_KEY: API_KEY,
            CONF_ACCOUNT: ACCOUNT_2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_as_subentry"


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


async def test_add_friend_flow(hass: HomeAssistant, steam_api: MagicMock) -> None:
    """Test add friend subentry flow."""
    steam_api.return_value.GetPlayerSummaries.return_value = (
        await async_load_json_object_fixture(
            hass, "GetPlayerSummariesSingle.json", DOMAIN
        )
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=ACCOUNT_NAME_1,
        data=CONF_DATA,
        unique_id=ACCOUNT_1,
        version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT_2},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={},
            subentry_id=subentry_id,
            subentry_type=SUBENTRY_TYPE_FRIEND,
            title=ACCOUNT_NAME_2,
            unique_id=ACCOUNT_2,
        )
    }


@pytest.mark.usefixtures("steam_api")
async def test_add_friend_flow_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test add friend subentry flow."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
        data={CONF_ACCOUNT: ACCOUNT_2},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("steam_api")
async def test_add_friend_flow_already_configured_as_entry(hass: HomeAssistant) -> None:
    """Test add friend subentry flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=ACCOUNT_NAME_1,
        data=CONF_DATA,
        unique_id=ACCOUNT_1,
        version=3,
    )
    MockConfigEntry(
        domain=DOMAIN,
        title=ACCOUNT_NAME_2,
        data=CONF_DATA,
        unique_id=ACCOUNT_2,
        version=3,
    ).add_to_hass(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT_2},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_as_entry"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (
            steam.api.HTTPError("Server connection failed: Unauthorized (401)"),
            "friendlist_private",
        ),
        (
            steam.api.HTTPError,
            "cannot_connect",
        ),
        (
            steam.api.HTTPTimeoutError,
            "timeout_connect",
        ),
        (
            ValueError,
            "unknown",
        ),
    ],
)
async def test_add_friend_flow_abort_errors(
    hass: HomeAssistant,
    steam_api: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: type[Exception] | Exception,
    reason: str,
) -> None:
    """Test add friend subentry flow aborts on errors."""

    steam_api.return_value.GetFriendList.side_effect = side_effect

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_add_friend_flow_abort_no_more_friends(
    hass: HomeAssistant,
    steam_api: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test add friend subentry flow aborts when no more friends left to add."""

    steam_api.return_value.GetPlayerSummaries.return_value = (
        await async_load_json_object_fixture(
            hass, "GetPlayerSummariesSingle.json", DOMAIN
        )
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_more_friends"


@pytest.mark.usefixtures("steam_api")
async def test_add_friend_flow_config_entry_not_loaded(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test add friend subentry flow."""
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_loaded"


@pytest.mark.parametrize(
    ("side_effect", "error_msg"),
    [
        (steam.api.HTTPTimeoutError, "timeout_connect"),
        (steam.api.HTTPError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_add_friend_errors(
    hass: HomeAssistant,
    steam_api: MagicMock,
    side_effect: type[Exception],
    error_msg: str,
) -> None:
    """Test add friend subentry flow with recoverable errors."""

    player_summaries = await async_load_json_object_fixture(
        hass, "GetPlayerSummariesSingle.json", DOMAIN
    )
    steam_api.return_value.GetPlayerSummaries.return_value = player_summaries

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=ACCOUNT_NAME_1,
        data=CONF_DATA,
        unique_id=ACCOUNT_1,
        version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_FRIEND),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    steam_api.return_value.GetPlayerSummaries.side_effect = [
        side_effect,
        player_summaries,
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT_2},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    steam_api.return_value.GetPlayerSummaries.side_effect = None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT_2},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    assert config_entry.subentries == {
        subentry_id: ConfigSubentry(
            data={},
            subentry_id=subentry_id,
            subentry_type=SUBENTRY_TYPE_FRIEND,
            title=ACCOUNT_NAME_2,
            unique_id=ACCOUNT_2,
        )
    }


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
