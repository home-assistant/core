"""Test Lastfm config flow."""
from pylast import WSError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.lastfm.const import (
    CONF_MAIN_USER,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_KEY,
    CONF_DATA,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    USERNAME_1,
    USERNAME_2,
    patch_fetch_user,
    patch_setup_entry,
)

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    with patch_fetch_user(), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
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
async def test_flow_fails(hass: HomeAssistant, error: Exception, message: str) -> None:
    """Test user initialized flow with invalid username."""
    with patch_fetch_user(thrown_error=error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == message

    with patch_fetch_user(), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_flow_friends_invalid_username(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid username."""
    with patch_fetch_user(), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "friends"

    with patch_fetch_user(thrown_error=WSError("network", "status", "User not found")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "friends"
        assert result["errors"]["base"] == "invalid_account"

    with patch_fetch_user(), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_flow_friends_no_friends(hass: HomeAssistant) -> None:
    """Test options is empty when user has no friends."""
    with patch_fetch_user(has_friends=False), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "friends"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow."""
    with patch_fetch_user():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_API_KEY: API_KEY, CONF_USERS: [USERNAME_1, USERNAME_2]},
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "LastFM"
    assert result["options"] == {
        "api_key": "asdasdasdasdasd",
        "main_user": None,
        "users": ["testaccount1", "testaccount2"],
    }


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_API_KEY: API_KEY, CONF_USERS: ["test"]},
    ).add_to_hass(hass)

    with patch_fetch_user():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: USERNAME_1,
            CONF_USERS: [USERNAME_1, USERNAME_2],
        },
    )
    entry.add_to_hass(hass)
    with patch_fetch_user():
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
    }


async def test_options_flow_incorrect_username(hass: HomeAssistant) -> None:
    """Test updating options doesn't work with incorrect username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: USERNAME_1,
            CONF_USERS: [USERNAME_1],
        },
    )
    entry.add_to_hass(hass)
    with patch_fetch_user():
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

    with patch_fetch_user(thrown_error=WSError("network", "status", "User not found")):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "invalid_account"

    with patch_fetch_user():
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
    }


async def test_options_flow_from_import(hass: HomeAssistant) -> None:
    """Test updating options gained from import."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: None,
            CONF_USERS: [USERNAME_1],
        },
    )
    entry.add_to_hass(hass)
    with patch_fetch_user():
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_options_flow_without_friends(hass: HomeAssistant) -> None:
    """Test updating options for someone without friends."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: USERNAME_1,
            CONF_USERS: [USERNAME_1],
        },
    )
    entry.add_to_hass(hass)
    with patch_fetch_user(has_friends=False):
        await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0
