"""Test Lastfm config flow."""

from unittest.mock import patch

from pylast import WSError
import pytest

from homeassistant.components.lastfm.config_flow import CONF_REDIRECT_URL
from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
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
    AUTH_URL,
    CONF_DATA,
    CONF_DATA_WITH_SESSION_KEY,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    CONF_USER_DATA_WITH_SECRET,
    REDIRECT_URL,
    USERNAME_1,
    MockSessionKeyGenerator,
    MockUser,
    patch_setup_entry,
)
from .conftest import ComponentSetup

from tests.common import MockConfigEntry

SESSION_KEY_GENERATOR_PATH = (
    "homeassistant.components.lastfm.config_flow.SessionKeyGenerator"
)


@pytest.mark.parametrize(
    "user_data",
    [
        pytest.param(CONF_USER_DATA, id="no_secret"),
        pytest.param({**CONF_USER_DATA, CONF_API_SECRET: ""}, id="empty_secret"),
    ],
)
async def test_full_user_flow(
    hass: HomeAssistant, default_user: MockUser, user_data: dict[str, str]
) -> None:
    """Test the full user configuration flow."""
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_data,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_full_user_flow_with_session_key(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test the full user configuration flow with web authentication."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(),
        ),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA_WITH_SECRET,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "auth_url"
        assert result["description_placeholders"]["auth_url"] == AUTH_URL

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REDIRECT_URL: REDIRECT_URL},
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA_WITH_SESSION_KEY


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
        (Exception(), "unknown"),
    ],
)
async def test_flow_web_auth_fails(
    hass: HomeAssistant, error: Exception, message: str, default_user: MockUser
) -> None:
    """Test user flow when starting web authentication fails."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(web_auth_url_error=error),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == message

    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(),
        ),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA_WITH_SECRET,
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "auth_url"


async def test_flow_invalid_redirect_url(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test web auth step rejects a redirect URL without a token."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(),
        ),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REDIRECT_URL: "https://www.example.com/callback"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_url"
        assert result["errors"]["base"] == "invalid_url"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REDIRECT_URL: REDIRECT_URL},
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (WSError("network", "17", "Unauthorized Token"), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_flow_token_exchange_fails(
    hass: HomeAssistant, error: Exception, message: str, default_user: MockUser
) -> None:
    """Test web auth step when exchanging the token for a session key fails."""
    mock_session_key_generator = MockSessionKeyGenerator(session_key_error=error)
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=mock_session_key_generator,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REDIRECT_URL: REDIRECT_URL},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_url"
        assert result["errors"]["base"] == message

    mock_session_key_generator.session_key_error = None
    with patch("pylast.User", return_value=default_user), patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REDIRECT_URL: REDIRECT_URL},
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "friends"


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
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


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
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA
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


async def test_flow_hidden_user_with_secret(hass: HomeAssistant) -> None:
    """Test a hidden user is accepted when an API secret is provided."""
    with (
        patch(
            "pylast.User",
            return_value=MockUser(
                recent_tracks_error=WSError(
                    "network", "17", "Login: User required to be logged in"
                )
            ),
        ),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(),
        ),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "auth_url"


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
