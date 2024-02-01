"""Test Lastfm config flow."""
from unittest.mock import patch

from pylast import WSError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.lastfm.const import (
    CONF_MAIN_USER,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import (
    API_KEY,
    CONF_DATA,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    USERNAME_1,
    MockUser,
    patch_setup_entry,
)
from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant, default_user: MockUser) -> None:
    """Test the full user configuration flow."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
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
async def test_flow_fails(
    hass: HomeAssistant, error: Exception, message: str, default_user: MockUser
) -> None:
    """Test user initialized flow with invalid username."""
    with patch("pylast.User", return_value=MockUser(thrown_error=error)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == message

    with patch("pylast.User", return_value=default_user), patch_setup_entry():
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


async def test_flow_friends_invalid_username(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test user initialized flow with invalid username."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
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

    with patch(
        "pylast.User",
        return_value=MockUser(
            thrown_error=WSError("network", "status", "User not found")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "friends"
        assert result["errors"]["base"] == "invalid_account"

    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_flow_friends_no_friends(
    hass: HomeAssistant, default_user_no_friends: MockUser
) -> None:
    """Test options is empty when user has no friends."""
    with patch(
        "pylast.User", return_value=default_user_no_friends
    ), patch_setup_entry():
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


async def test_options_flow(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test updating options."""
    await setup_integration(config_entry, default_user)
    with patch("pylast.User", return_value=default_user):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
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


async def test_options_flow_incorrect_username(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test updating options doesn't work with incorrect username."""
    await setup_integration(config_entry, default_user)
    with patch("pylast.User", return_value=default_user):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

    with patch(
        "pylast.User",
        return_value=MockUser(
            thrown_error=WSError("network", "status", "User not found")
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "invalid_account"

    with patch("pylast.User", return_value=default_user):
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


async def test_options_flow_from_import(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    imported_config_entry: MockConfigEntry,
    default_user_no_friends: MockUser,
) -> None:
    """Test updating options gained from import."""
    await setup_integration(imported_config_entry, default_user_no_friends)
    with patch("pylast.User", return_value=default_user_no_friends):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_options_flow_without_friends(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user_no_friends: MockUser,
) -> None:
    """Test updating options for someone without friends."""
    await setup_integration(config_entry, default_user_no_friends)
    with patch("pylast.User", return_value=default_user_no_friends):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0
