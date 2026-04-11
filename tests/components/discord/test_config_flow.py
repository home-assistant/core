"""Test the Discord config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import nextcord

from homeassistant import config_entries
from homeassistant.components.discord.const import (
    CONF_CHANNEL_ID,
    DOMAIN,
    SUBENTRY_TYPE_CHANNEL,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    BOT_ID,
    BOT_NAME,
    CHANNEL_ID,
    CHANNEL_NAME,
    CONF_DATA,
    CONF_INPUT,
    create_entry,
    mocked_discord_info,
    patch_discord_close,
    patch_discord_login,
)

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_init_login():
    """Patch the nextcord.Client used in __init__.async_setup_entry."""
    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    return patch(
        "homeassistant.components.discord.__init__.nextcord.Client",
        return_value=bot,
    )


# ---------------------------------------------------------------------------
# User flow
# ---------------------------------------------------------------------------


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test the happy-path user flow creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BOT_NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test duplicate detection aborts the flow."""
    create_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test an invalid token shows an error then lets the user retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch_discord_login() as mock_login,
        patch_discord_close(),
    ):
        mock_login.side_effect = nextcord.LoginFailure
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test a connection failure shows an error then lets the user retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch_discord_login() as mock_login,
        patch_discord_close(),
    ):
        mock_login.side_effect = nextcord.HTTPException(MagicMock(), "")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test an unexpected exception shows an 'unknown' error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch_discord_login() as mock_login,
        patch_discord_close(),
    ):
        mock_login.side_effect = Exception("boom")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Reauth flow
# ---------------------------------------------------------------------------


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test the reauth flow updates the token."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_token = {CONF_API_TOKEN: "new-token-abc"}

    with (
        patch_discord_login() as mock_login,
        patch_discord_close(),
    ):
        mock_login.side_effect = nextcord.LoginFailure
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_token
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_token
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "new-token-abc"


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


async def test_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test the reconfigure flow updates the token and title."""
    entry = create_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_token = {CONF_API_TOKEN: "reconfigured-token"}

    with mocked_discord_info(), patch_discord_login(), patch_discord_close():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_token
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_TOKEN] == "reconfigured-token"


# ---------------------------------------------------------------------------
# Channel subentry flow
# ---------------------------------------------------------------------------


async def test_subentry_add_channel(hass: HomeAssistant) -> None:
    """Test adding a channel subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    # Set up entry so it's LOADED and runtime_data is available.
    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_channel = MagicMock()
    mock_channel.name = CHANNEL_NAME

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(return_value=mock_channel)

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: str(CHANNEL_ID)}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CHANNEL_NAME
    assert result["data"] == {CONF_CHANNEL_ID: CHANNEL_ID}


async def test_subentry_channel_not_found(hass: HomeAssistant) -> None:
    """Test that an invalid channel ID shows an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(side_effect=nextcord.NotFound(MagicMock(), ""))
    bot.fetch_user = AsyncMock(side_effect=nextcord.NotFound(MagicMock(), ""))

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: "9999"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "channel_not_found"}


async def test_subentry_already_configured(hass: HomeAssistant) -> None:
    """Test that adding a duplicate channel is aborted."""
    entry = create_entry(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    mock_channel = MagicMock()
    mock_channel.name = CHANNEL_NAME

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(return_value=mock_channel)

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: str(CHANNEL_ID)}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_add_channel_invalid_id(hass: HomeAssistant) -> None:
    """Test that a non-numeric channel ID shows a channel_not_found error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={CONF_CHANNEL_ID: "not-a-number"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "channel_not_found"}


async def test_subentry_add_dm_user_success(hass: HomeAssistant) -> None:
    """Test that fetch_channel NotFound falls back to fetch_user in the subentry flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    mock_user = MagicMock()
    mock_user.name = "testuser"

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(side_effect=nextcord.NotFound(MagicMock(), ""))
    bot.fetch_user = AsyncMock(return_value=mock_user)

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: "1111111111"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "testuser"


async def test_subentry_add_channel_entry_not_loaded(hass: HomeAssistant) -> None:
    """Test that starting a subentry flow when the entry is not loaded aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    # Do NOT call async_setup — entry stays in NOT_LOADED state.

    # async_step_user checks the state immediately (even before showing the form)
    # so async_init returns ABORT directly.
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_subentry_channel_forbidden(hass: HomeAssistant) -> None:
    """Test that a Forbidden error shows a cannot_access_channel error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(side_effect=nextcord.Forbidden(MagicMock(), ""))

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: str(CHANNEL_ID)}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_access_channel"}


async def test_subentry_channel_http_error(hass: HomeAssistant) -> None:
    """Test that an HTTP error shows a cannot_connect error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with _patch_init_login():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": config_entries.SOURCE_USER},
    )

    bot = MagicMock()
    bot.login = AsyncMock()
    bot.close = AsyncMock()
    bot.fetch_channel = AsyncMock(
        side_effect=nextcord.HTTPException(MagicMock(), "rate limited")
    )

    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client",
        return_value=bot,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_CHANNEL_ID: str(CHANNEL_ID)}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reconfigure_invalid_auth(hass: HomeAssistant) -> None:
    """Test that an auth error during reconfigure shows an error."""
    entry = create_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch_discord_login() as mock_login,
        patch_discord_close(),
    ):
        mock_login.side_effect = nextcord.LoginFailure
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_TOKEN: "bad-token"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
