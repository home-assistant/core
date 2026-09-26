"""Test Discord config flow."""

from unittest.mock import AsyncMock, Mock, patch

import nextcord
import pytest

from homeassistant import config_entries
from homeassistant.components.discord.const import (
    CONF_TARGET_ID,
    DOMAIN,
    SUBENTRY_TYPE_TARGET,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    CONF_DATA,
    CONF_INPUT,
    NAME,
    TARGET_NAME,
    create_entry,
    mock_exception,
    mocked_discord_info,
    patch_discord_login,
)
from .conftest import TARGET


def _patch_fetch_channel(
    return_value: Mock | None = None, side_effect: Exception | None = None
):
    """Patch fetching a Discord channel."""
    return patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.fetch_channel",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def _patch_fetch_user(
    return_value: Mock | None = None, side_effect: Exception | None = None
):
    """Patch fetching a Discord user for a DM."""
    return patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.fetch_user",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


def _patch_close():
    """Patch closing the Discord client."""
    return patch("homeassistant.components.discord.config_flow.nextcord.Client.close")


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid token."""
    with patch_discord_login() as mock:
        mock.side_effect = nextcord.LoginFailure
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_discord_login() as mock:
        mock.side_effect = mock_exception()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_discord_login() as mock:
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test a reauth flow."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_conf = {CONF_API_TOKEN: "1234567890123"}
    with patch_discord_login() as mock:
        mock.side_effect = nextcord.LoginFailure
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    with mocked_discord_info(), patch_discord_login():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == CONF_DATA | new_conf


async def test_subentry_flow_target(hass: HomeAssistant) -> None:
    """Test adding a target through the subentry flow."""
    entry = create_entry(hass)
    channel = Mock()
    channel.name = TARGET_NAME

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TARGET),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_discord_login(), _patch_fetch_channel(channel), _patch_close():
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_TARGET_ID: TARGET},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TARGET_NAME
    assert result["data"] == {CONF_TARGET_ID: TARGET}
    assert result["unique_id"] == TARGET


async def test_subentry_flow_invalid_target(hass: HomeAssistant) -> None:
    """Test a non-numeric target ID is rejected before contacting Discord."""
    entry = create_entry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TARGET),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TARGET_ID: "not-a-number"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_target"}


async def test_subentry_flow_user_fallback(hass: HomeAssistant) -> None:
    """Test resolving a target that is a user (DM) rather than a channel."""
    entry = create_entry(hass)
    user = Mock()
    user.name = "some_user"

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TARGET),
        context={"source": SOURCE_USER},
    )

    with (
        patch_discord_login(),
        _patch_fetch_channel(side_effect=nextcord.NotFound(Mock(status=404), "")),
        _patch_fetch_user(user),
        _patch_close(),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_TARGET_ID: TARGET},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "some_user"


async def test_subentry_flow_already_configured(hass: HomeAssistant) -> None:
    """Test adding a target that is already configured aborts."""
    entry = create_entry(hass, with_subentry=True)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TARGET),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_TARGET_ID: TARGET},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("login_side_effect", "channel_side_effect", "user_side_effect", "expected_error"),
    [
        (nextcord.LoginFailure, None, None, "invalid_auth"),
        (mock_exception(), None, None, "cannot_connect"),
        (
            None,
            nextcord.NotFound(Mock(status=404), ""),
            nextcord.NotFound(Mock(status=404), ""),
            "target_not_found",
        ),
        (None, Exception, None, "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "target_not_found", "unknown"],
)
async def test_subentry_flow_errors(
    hass: HomeAssistant,
    login_side_effect: Exception | None,
    channel_side_effect: Exception | None,
    user_side_effect: Exception | None,
    expected_error: str,
) -> None:
    """Test error handling in the target subentry flow."""
    entry = create_entry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TARGET),
        context={"source": SOURCE_USER},
    )

    with (
        patch_discord_login() as login,
        _patch_fetch_channel(side_effect=channel_side_effect),
        _patch_fetch_user(side_effect=user_side_effect),
        _patch_close(),
    ):
        login.side_effect = login_side_effect
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_TARGET_ID: TARGET},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    channel = Mock()
    channel.name = TARGET_NAME
    with patch_discord_login(), _patch_fetch_channel(channel), _patch_close():
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_TARGET_ID: TARGET},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TARGET_NAME
    assert result["data"] == {CONF_TARGET_ID: TARGET}
