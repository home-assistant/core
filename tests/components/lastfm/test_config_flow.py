"""Test Lastfm config flow."""

from unittest.mock import create_autospec, patch

from pylast import LastFMNetwork, PyLastError, SessionKeyGenerator, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.lastfm.config_flow import get_auth_url, get_session_key
from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEYS,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_KEY,
    API_SECRET,
    AUTH_URL,
    CONF_DATA,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    SESSION_KEYS,
    USERNAME_1,
    USERNAME_2,
    MockUser,
    patch_setup_entry,
)
from .conftest import ComponentSetup

CONFIG_FLOW = "homeassistant.components.lastfm.config_flow"


def patch_generator(session: tuple[str, str] | None = None):
    """Patch pylast's SessionKeyGenerator, keeping the integration helpers real."""
    generator = create_autospec(SessionKeyGenerator, instance=True)
    generator.get_web_auth_url.return_value = AUTH_URL
    generator.get_web_auth_session_key_username.return_value = session
    return patch(f"{CONFIG_FLOW}.SessionKeyGenerator", return_value=generator)


async def _select_step(
    hass: HomeAssistant, result: ConfigFlowResult, next_step_id: str
) -> ConfigFlowResult:
    """Pick an option of a menu."""
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": next_step_id}
    )


async def _start_flow_to_menu(hass: HomeAssistant) -> ConfigFlowResult:
    """Run the user and friends steps and return the scrobbling menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_USER_DATA
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_FRIENDS_DATA
    )


async def _authorize_from_form(
    hass: HomeAssistant,
    form: ConfigFlowResult,
    username: str,
    *,
    secret: str | None = None,
    authorized_as: str | None = None,
) -> ConfigFlowResult:
    """Authorize a user starting from the scrobble_user form."""
    user_input = {CONF_USERNAME: username}
    if secret:
        user_input[CONF_API_SECRET] = secret
    with patch(f"{CONFIG_FLOW}.get_auth_url", return_value=AUTH_URL):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], user_input=user_input
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"
    assert result["description_placeholders"]["auth_url"] == AUTH_URL
    with patch(
        f"{CONFIG_FLOW}.get_session_key",
        return_value=(SESSION_KEYS[username], authorized_as or username),
    ):
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )


async def _authorize(
    hass: HomeAssistant, menu: ConfigFlowResult, username: str, **kwargs: str
) -> ConfigFlowResult:
    """Authorize a user from a menu offering scrobble_user."""
    form = await _select_step(hass, menu, "scrobble_user")
    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "scrobble_user"
    return await _authorize_from_form(hass, form, username, **kwargs)


async def test_full_user_flow(hass: HomeAssistant, default_user: MockUser) -> None:
    """Test the full user configuration flow without scrobbling."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"
        assert result["data_schema"].schema[CONF_USERS].config["options"] == [
            USERNAME_1
        ]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "scrobble_menu"
        assert result["menu_options"] == ["scrobble_user", "finish"]

        result = await _select_step(hass, result, "finish")
        assert result["type"] is FlowResultType.CREATE_ENTRY
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
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == message

    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.MENU

        result = await _select_step(hass, result, "finish")
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


def test_authorization_helpers() -> None:
    """Test the helpers pass credentials and the token to pylast."""
    session = (SESSION_KEYS[USERNAME_1], USERNAME_1)
    with patch_generator(session) as mock_generator:
        assert get_auth_url(API_KEY, API_SECRET) == AUTH_URL
        assert get_session_key(API_KEY, API_SECRET, AUTH_URL) == session

    for call in mock_generator.call_args_list:
        network = call.args[0]
        assert isinstance(network, LastFMNetwork)
        assert (network.api_key, network.api_secret) == (API_KEY, API_SECRET)
    generator = mock_generator.return_value
    generator.get_web_auth_session_key_username.assert_called_once_with(
        AUTH_URL, "token"
    )


async def test_flow_hidden_recent_tracks(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test user initialized flow when user hides recent listening information."""
    with patch(
        "pylast.User",
        return_value=MockUser(
            recent_tracks_error=WSError(
                "network", "17", "Login: User required to be logged in"
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "hidden_recent_tracks"

    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.MENU

        result = await _select_step(hass, result, "finish")
        assert result["type"] is FlowResultType.CREATE_ENTRY


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
        assert result["type"] is FlowResultType.FORM
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"
        assert result["errors"]["base"] == "invalid_account"

    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.MENU

        result = await _select_step(hass, result, "finish")
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_flow_friends_no_friends(
    hass: HomeAssistant, default_user_no_friends: MockUser
) -> None:
    """Test options is empty when user has no friends."""
    with (
        patch("pylast.User", return_value=default_user_no_friends),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0


async def test_flow_scrobbling_two_users(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test authorizing two users for scrobbling during setup."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        menu = await _start_flow_to_menu(hass)
        assert menu["description_placeholders"]["authorized_users"] == "–"

        # First user: the API secret is requested
        result = await _select_step(hass, menu, "scrobble_user")
        assert CONF_API_SECRET in result["data_schema"].schema
        assert result["data_schema"].schema[CONF_USERNAME].config["options"] == [
            {"value": USERNAME_1, "label": USERNAME_1},
            {"value": USERNAME_2, "label": USERNAME_2},
        ]

        menu = await _authorize_from_form(hass, result, USERNAME_1, secret=API_SECRET)
        assert menu["type"] is FlowResultType.MENU
        assert menu["step_id"] == "scrobble_menu"
        assert menu["menu_options"] == ["scrobble_user", "finish"]
        assert menu["description_placeholders"]["authorized_users"] == (
            f"**{USERNAME_1}**"
        )

        # Second user: secret is remembered, authorized user is not offered again
        result = await _select_step(hass, menu, "scrobble_user")
        assert CONF_API_SECRET not in result["data_schema"].schema
        assert result["data_schema"].schema[CONF_USERNAME].config["options"] == [
            {"value": USERNAME_1, "label": f"{USERNAME_1} ✓"},
            {"value": USERNAME_2, "label": USERNAME_2},
        ]

        menu = await _authorize_from_form(hass, result, USERNAME_2)
        assert menu["menu_options"] == ["scrobble_user", "finish"]
        assert menu["description_placeholders"]["authorized_users"] == (
            f"**{USERNAME_1}**, **{USERNAME_2}**"
        )

        result = await _select_step(hass, menu, "finish")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        **CONF_DATA,
        CONF_API_SECRET: API_SECRET,
        CONF_SESSION_KEYS: SESSION_KEYS,
    }


@pytest.mark.parametrize(
    "session_key_patch",
    [
        pytest.param(
            {"side_effect": WSError("network", "14", "Unauthorized Token")},
            id="not_allowed",
        ),
        pytest.param(
            {"side_effect": PyLastError("network", "status", "Failure")},
            id="other_error",
        ),
        pytest.param(
            {"return_value": (SESSION_KEYS[USERNAME_1], "someoneelse")},
            id="account_mismatch",
        ),
    ],
)
async def test_flow_scrobbling_authorization_fails(
    hass: HomeAssistant,
    default_user: MockUser,
    session_key_patch: dict,
) -> None:
    """Test a failed authorization offers a retry and a way back."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        menu = await _start_flow_to_menu(hass)

        result = await _select_step(hass, menu, "scrobble_user")
        with patch(f"{CONFIG_FLOW}.get_auth_url", return_value=AUTH_URL):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: USERNAME_1, CONF_API_SECRET: API_SECRET},
            )
        assert result["step_id"] == "authorize"

        with patch(f"{CONFIG_FLOW}.get_session_key", **session_key_patch):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "scrobble_failed"
        assert result["menu_options"] == ["scrobble_user", "scrobble_menu"]

        # Nobody was authorized, so the unproven secret is requested again
        retry = await _select_step(hass, result, "scrobble_user")
        assert retry["step_id"] == "scrobble_user"
        assert CONF_API_SECRET in retry["data_schema"].schema


async def test_flow_scrobbling_back_and_finish(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test going back after a failure and finishing without scrobbling."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        menu = await _start_flow_to_menu(hass)

        result = await _select_step(hass, menu, "scrobble_user")
        with patch(
            f"{CONFIG_FLOW}.get_auth_url",
            side_effect=PyLastError("network", "status", "Failure"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: USERNAME_1, CONF_API_SECRET: API_SECRET},
            )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "scrobble_failed"

        result = await _select_step(hass, result, "scrobble_menu")
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "scrobble_menu"

        result = await _select_step(hass, result, "finish")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == CONF_DATA


async def test_reconfigure_enable_scrobbling(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test enabling scrobbling for an existing entry."""
    await setup_integration(config_entry, default_user)
    with patch("pylast.User", return_value=default_user):
        result = await config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "scrobble_menu"
        assert result["description_placeholders"]["authorized_users"] == "–"

        result = await _authorize(hass, result, USERNAME_2, secret=API_SECRET)
        result = await _select_step(hass, result, "finish")
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.options == {
        **CONF_DATA,
        CONF_API_SECRET: API_SECRET,
        CONF_SESSION_KEYS: {USERNAME_2: SESSION_KEYS[USERNAME_2]},
    }


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

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["data_schema"].schema[CONF_USERS].config["options"] == [
            USERNAME_1
        ]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
        CONF_SESSION_KEYS: {},
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

        assert result["type"] is FlowResultType.FORM
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

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "invalid_account"

    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
        CONF_SESSION_KEYS: {},
    }


async def test_options_flow_hidden_recent_tracks(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test updating options fails when user hides recent listening information."""
    await setup_integration(config_entry, default_user)
    with patch("pylast.User", return_value=default_user):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

    with patch(
        "pylast.User",
        return_value=MockUser(
            recent_tracks_error=WSError(
                "network", "17", "Login: User required to be logged in"
            )
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"]["base"] == "hidden_recent_tracks"

    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERS: [USERNAME_1]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


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

        assert result["type"] is FlowResultType.FORM
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

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert len(result["data_schema"].schema[CONF_USERS].config["options"]) == 0
