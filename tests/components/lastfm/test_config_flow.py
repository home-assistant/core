"""Test Lastfm config flow."""

from unittest.mock import MagicMock, call, patch

from pylast import MalformedResponseError, NetworkError, WSError
import pytest

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
    ERROR_CODE_TOKEN_UNAUTHORIZED,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_KEY,
    API_SECRET,
    AUTH_URL,
    CONF_DATA,
    CONF_DATA_WITH_SESSION_KEY,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    CONF_USER_DATA_WITH_SECRET,
    NEW_SESSION_KEY,
    SESSION_KEY,
    USERNAME_1,
    USERNAME_2,
    MockSessionKeyGenerator,
    MockUser,
    get_session_key_polling_task,
    patch_setup_entry,
)
from .conftest import ComponentSetup

from tests.common import MockConfigEntry

FLOW_MODULE = "homeassistant.components.lastfm.config_flow"
SESSION_KEY_GENERATOR_PATH = f"{FLOW_MODULE}.SessionKeyGenerator"
POLLING_INTERVAL_PATH = f"{FLOW_MODULE}.POLLING_INTERVAL"
MAX_POLLING_ATTEMPTS_PATH = f"{FLOW_MODULE}.MAX_POLLING_ATTEMPTS"


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
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 0),
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
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"
        assert result["url"] == AUTH_URL

        await get_session_key_polling_task()
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA_WITH_SESSION_KEY


async def test_flow_rejects_session_for_different_user(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test a session for a different Last.fm user is rejected."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(session_username=USERNAME_2),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert result["description_placeholders"] == {
        "authorized_user": USERNAME_2,
        "configured_user": USERNAME_1,
    }


async def test_flow_restarts_polling_after_timeout(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test polling restarts when the user continues after a timeout."""
    session_key_generator = MockSessionKeyGenerator(
        session_key_error=WSError(
            "network", ERROR_CODE_TOKEN_UNAUTHORIZED, "Unauthorized Token"
        )
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=session_key_generator),
        patch(POLLING_INTERVAL_PATH, 0),
        patch(MAX_POLLING_ATTEMPTS_PATH, 1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await get_session_key_polling_task()
        await hass.async_block_till_done()

        session_key_generator.session_key_error = None
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await get_session_key_polling_task()
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "friends"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WSError("network", "15", "Token expired"), id="expired_token"),
        pytest.param(Exception(), id="unexpected_error"),
    ],
)
async def test_flow_session_key_error(
    hass: HomeAssistant, default_user: MockUser, error: Exception
) -> None:
    """Test terminal session key errors abort the flow."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(session_key_error=error),
        ),
        patch(POLLING_INTERVAL_PATH, 0),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await get_session_key_polling_task()
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"


async def test_reauth_flow(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test replacing an invalid Last.fm session key."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(session_key=NEW_SESSION_KEY),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert authenticated_config_entry.options == {
        **CONF_DATA_WITH_SESSION_KEY,
        CONF_SESSION_KEY: NEW_SESSION_KEY,
    }


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication rejects a different Last.fm account."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(session_username=USERNAME_2),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reauth_flow_session_key_error(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test a terminal session exchange error aborts reauthentication."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(
                session_key_error=WSError("network", "15", "Token expired")
            ),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reauth_flow_start_error(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test failing to start web authentication aborts reauthentication."""
    authenticated_config_entry.add_to_hass(hass)
    with patch(
        SESSION_KEY_GENERATOR_PATH,
        return_value=MockSessionKeyGenerator(
            web_auth_url_error=WSError("network", "10", "Invalid API key")
        ),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reauth_flow_start_retry(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
) -> None:
    """Test retrying a transient web authentication start failure."""
    session_key_generator = MockSessionKeyGenerator(
        web_auth_url_error=WSError("network", "16", "Service unavailable")
    )
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(SESSION_KEY_GENERATOR_PATH, return_value=session_key_generator),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

        session_key_generator.web_auth_url_error = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    polling_task = get_session_key_polling_task()
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert polling_task.cancelled()


async def test_flow_abort_cancels_session_key_polling(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test aborting the flow cancels session key polling."""
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        polling_task = get_session_key_polling_task()

        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    assert polling_task.cancelled()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            WSError(
                "network",
                "10",
                "Invalid API key - You must be granted a valid key by last.fm",
            ),
            "invalid_auth",
        ),
        (WSError("network", "16", "Service unavailable"), "cannot_connect"),
        (NetworkError("network", Exception()), "cannot_connect"),
        (WSError("network", "2", "Invalid service"), "unknown"),
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
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_USER_DATA_WITH_SECRET,
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME


@pytest.mark.parametrize(
    "session_key_error",
    [
        pytest.param(
            WSError("network", ERROR_CODE_TOKEN_UNAUTHORIZED, "Unauthorized Token"),
            id="pending_authorization",
        ),
        pytest.param(
            WSError("network", "16", "Service unavailable"),
            id="temporarily_unavailable",
        ),
        pytest.param(
            NetworkError("network", Exception()),
            id="network_error",
        ),
        pytest.param(
            MalformedResponseError("network", Exception()),
            id="malformed_response",
        ),
    ],
)
async def test_flow_waits_for_authorization(
    hass: HomeAssistant,
    default_user: MockUser,
    session_key_error: Exception,
) -> None:
    """Test the flow waits until the Last.fm authorization is granted."""
    mock_session_key_generator = MockSessionKeyGenerator(
        session_key_error=session_key_error
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=mock_session_key_generator,
        ),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        mock_session_key_generator.session_key_error = None
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
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
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USERS: []}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"] == {
            **CONF_DATA_WITH_SESSION_KEY,
            CONF_USERS: [USERNAME_1],
        }


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


async def test_options_flow_with_session_key(
    hass: HomeAssistant,
    default_user: MockUser,
    hidden_user: MockUser,
) -> None:
    """Test options validation accepts a hidden user with a saved session."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options=CONF_DATA_WITH_SESSION_KEY,
    )
    config_entry.add_to_hass(hass)
    anonymous_network = MagicMock()
    anonymous_network.get_user.return_value = hidden_user
    authenticated_network = MagicMock()
    authenticated_network.get_user.return_value = default_user
    with (
        patch(
            f"{FLOW_MODULE}.LastFMNetwork",
            side_effect=[anonymous_network, authenticated_network],
        ) as network_cls,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_USERS: [USERNAME_1]}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **CONF_DATA_WITH_SESSION_KEY,
        CONF_USERS: [USERNAME_1],
    }
    network_cls.assert_has_calls(
        [
            call(api_key=API_KEY, api_secret="", session_key=""),
            call(
                api_key=API_KEY,
                api_secret=API_SECRET,
                session_key=SESSION_KEY,
            ),
        ]
    )


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
