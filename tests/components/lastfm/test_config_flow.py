"""Test Lastfm config flow."""

import asyncio
from datetime import timedelta
from threading import Event
from unittest.mock import MagicMock, call, patch

from pylast import MalformedResponseError, NetworkError, PyLastError, WSError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
    DEFAULT_NAME,
    DOMAIN,
    ERROR_CODE_TOKEN_UNAUTHORIZED,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow
from homeassistant.util import dt as dt_util

from . import (
    API_KEY,
    API_SECRET,
    AUTH_URL,
    CONF_DATA,
    CONF_DATA_WITH_SESSION_KEY,
    CONF_FRIENDS_DATA,
    CONF_USER_DATA,
    CONF_USER_DATA_WITH_SECRET,
    LOGIN_REQUIRED_ERROR,
    NEW_SESSION_KEY,
    SESSION_KEY,
    USERNAME_1,
    USERNAME_2,
    BlockingAccountUser,
    BlockingUser,
    MockSessionKeyGenerator,
    MockUser,
    patch_setup_entry,
)
from .conftest import ComponentSetup

FLOW_MODULE = "homeassistant.components.lastfm.config_flow"
SESSION_KEY_GENERATOR_PATH = f"{FLOW_MODULE}.SessionKeyGenerator"
POLLING_INTERVAL_PATH = f"{FLOW_MODULE}.POLLING_INTERVAL"
MAX_POLLING_ATTEMPTS_PATH = f"{FLOW_MODULE}.MAX_POLLING_ATTEMPTS"


async def test_user_overlapping_candidates_keep_validated_credentials(
    hass: HomeAssistant,
    default_user: MockUser,
) -> None:
    """A rejected setup submission must not change another submission's credentials."""
    user = BlockingAccountUser()
    invalid_user = MockUser(
        thrown_error=WSError(
            "network",
            "10",
            "Invalid API key - You must be granted a valid key by last.fm",
        )
    )
    with (
        patch("pylast.User", side_effect=[user, invalid_user, default_user]),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        first_submission = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=CONF_USER_DATA
            )
        )
        try:
            assert await hass.async_add_executor_job(user.validation_started.wait, 5)
            invalid_result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={**CONF_USER_DATA, CONF_API_KEY: "invalid-api-key"},
            )
            assert invalid_result["errors"] == {"base": "invalid_auth"}
        finally:
            user.validation_release.set()
        result = await first_submission
        assert result["step_id"] == "friends"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USERS: []}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_API_KEY: API_KEY,
        CONF_MAIN_USER: USERNAME_1,
        CONF_USERS: [USERNAME_1],
    }


@pytest.mark.parametrize(
    ("stale_user_data", "stale_error"),
    [
        pytest.param(CONF_USER_DATA_WITH_SECRET, None, id="authenticated_submission"),
        pytest.param(CONF_USER_DATA, None, id="anonymous_submission"),
        pytest.param(
            CONF_USER_DATA_WITH_SECRET,
            WSError(
                "network",
                "10",
                "Invalid API key - You must be granted a valid key by last.fm",
            ),
            id="rejected_submission",
        ),
    ],
)
async def test_stale_user_submission_preserves_authenticated_friends_save(
    hass: HomeAssistant,
    default_user: MockUser,
    stale_user_data: dict[str, str],
    stale_error: WSError | None,
) -> None:
    """A delayed setup submission must not replace an authorized session."""
    stale_user = BlockingAccountUser(thrown_error=stale_error)
    friends_user = BlockingUser()
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        try:
            with patch("pylast.User", return_value=stale_user):
                stale_submission = hass.async_create_task(
                    hass.config_entries.flow.async_configure(
                        result["flow_id"], user_input=stale_user_data
                    )
                )
                assert await hass.async_add_executor_job(
                    stale_user.validation_started.wait, 5
                )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
            )
            assert result["type"] is FlowResultType.EXTERNAL_STEP
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            assert result["step_id"] == "friends"

            with patch("pylast.User", return_value=friends_user):
                friends_submission = hass.async_create_task(
                    hass.config_entries.flow.async_configure(
                        result["flow_id"], user_input=CONF_FRIENDS_DATA.copy()
                    )
                )
                assert await hass.async_add_executor_job(
                    friends_user.validation_started.wait, 5
                )

            stale_user.validation_release.set()
            stale_result = await stale_submission
        finally:
            stale_user.validation_release.set()
            friends_user.validation_release.set()

        result = await friends_submission
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == CONF_DATA_WITH_SESSION_KEY
    assert stale_result["type"] is FlowResultType.FORM
    assert stale_result["step_id"] == "friends"


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
        assert result["data_schema"].schema[CONF_USERS].config["options"] == [
            USERNAME_1
        ]

        with (
            patch.object(default_user, "get_playcount") as get_playcount,
            patch.object(default_user, "get_recent_tracks") as get_recent_tracks,
            patch.object(
                default_user, "get_friends", wraps=default_user.get_friends
            ) as get_friends,
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "friends"
            assert result["data_schema"].schema[CONF_USERS].config["options"] == [
                USERNAME_1
            ]
            get_friends.assert_called_once_with()
            get_playcount.assert_not_called()
            get_recent_tracks.assert_not_called()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_full_user_flow_with_session_key(
    hass: HomeAssistant,
    default_user: MockUser,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test the full user configuration flow with web authentication."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    with (
        patch("pylast.User", return_value=default_user),
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

        await hass.async_block_till_done()
        session_exchange.assert_not_called()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "friends"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FRIENDS_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA_WITH_SESSION_KEY


async def test_session_key_exchange_is_serialized(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test polling and Submit share one session exchange."""
    session_key_generator = MockSessionKeyGenerator()
    exchange_started = asyncio.Event()
    exchange_release = Event()

    def blocked_exchange(url: str, token: str = "") -> tuple[str, str]:
        """Wait for Submit before returning the session key and username."""
        hass.loop.call_soon_threadsafe(exchange_started.set)
        assert exchange_release.wait(5)
        return SESSION_KEY, USERNAME_1

    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=session_key_generator),
        patch.object(
            session_key_generator,
            "get_web_auth_session_key_username",
            side_effect=blocked_exchange,
        ) as session_exchange,
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        try:
            await exchange_started.wait()
            submit_task = hass.async_create_task(
                hass.config_entries.flow.async_configure(result["flow_id"])
            )
        finally:
            exchange_release.set()

        submit_result = await submit_task
        await hass.async_block_till_done(wait_background_tasks=True)
        assert submit_result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        session_exchange.assert_called_once_with(AUTH_URL)

        hass.config_entries.flow.async_abort(result["flow_id"])
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)


async def test_flow_rejects_session_for_different_user(
    hass: HomeAssistant,
    default_user: MockUser,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test a session for a different Last.fm user is rejected."""
    mock_session_key_generator.get_web_auth_session_key_username.return_value = (
        SESSION_KEY,
        USERNAME_2,
    )
    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
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
    hass: HomeAssistant,
    default_user: MockUser,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test polling restarts when the user continues after a timeout."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    session_exchange.side_effect = WSError(
        "network", ERROR_CODE_TOKEN_UNAUTHORIZED, "Unauthorized Token"
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(MAX_POLLING_ATTEMPTS_PATH, 1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

        session_exchange.side_effect = None
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"
        await hass.async_block_till_done()
        session_exchange.assert_called_once_with(AUTH_URL)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert session_exchange.call_args_list == [call(AUTH_URL), call(AUTH_URL)]

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "friends"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WSError("network", "15", "Token expired"), id="expired_token"),
        pytest.param(PyLastError("Library failure"), id="library_error"),
        pytest.param(Exception(), id="unexpected_error"),
    ],
)
async def test_flow_session_key_error(
    hass: HomeAssistant,
    default_user: MockUser,
    error: Exception,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test terminal session key errors abort the flow."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    session_exchange.side_effect = error
    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "auth_failed"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)


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
        ) as session_key_generator,
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] is None
        session_key_generator.assert_not_called()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] is None
        session_key_generator.assert_not_called()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"
        session_key_generator.assert_called_once()

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


@pytest.mark.parametrize(
    ("first_error", "first_type", "expected_url", "expected_requests"),
    [
        pytest.param(
            None, FlowResultType.EXTERNAL_STEP, AUTH_URL, 1, id="reuse_authorization"
        ),
        pytest.param(
            WSError("network", "16", "Service unavailable"),
            FlowResultType.FORM,
            f"{AUTH_URL}-second",
            2,
            id="retry_transient_error",
        ),
    ],
)
async def test_reauth_overlapping_confirmations(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    first_error: WSError | None,
    first_type: FlowResultType,
    expected_url: str,
    expected_requests: int,
) -> None:
    """Queued confirmations must preserve the first successful authorization."""
    authenticated_config_entry.add_to_hass(hass)
    first_generator = MockSessionKeyGenerator(
        web_auth_url_error=first_error, session_key=NEW_SESSION_KEY
    )
    second_generator = MockSessionKeyGenerator(session_key=NEW_SESSION_KEY)
    get_web_auth_url = first_generator.get_web_auth_url
    authorization_started = Event()
    authorization_release = Event()
    submissions: list[asyncio.Task[ConfigFlowResult]] = []

    def blocked_get_web_auth_url() -> str:
        """Wait for the second confirmation before returning the first token."""
        authorization_started.set()
        assert authorization_release.wait(5)
        return get_web_auth_url()

    with (
        patch(
            SESSION_KEY_GENERATOR_PATH,
            side_effect=[first_generator, second_generator],
        ) as session_key_generator,
        patch.object(
            first_generator, "get_web_auth_url", side_effect=blocked_get_web_auth_url
        ),
        patch.object(
            second_generator, "get_web_auth_url", return_value=f"{AUTH_URL}-second"
        ),
        patch.object(
            first_generator,
            "get_web_auth_session_key_username",
            wraps=first_generator.get_web_auth_session_key_username,
        ) as first_exchange,
        patch.object(
            second_generator,
            "get_web_auth_session_key_username",
            wraps=second_generator.get_web_auth_session_key_username,
        ) as second_exchange,
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await authenticated_config_entry.start_reauth_flow(hass)
        submissions.append(
            hass.async_create_task(
                hass.config_entries.flow.async_configure(
                    result["flow_id"], user_input={}
                )
            )
        )
        try:
            assert await hass.async_add_executor_job(authorization_started.wait, 5)
            submissions.append(
                hass.async_create_task(
                    hass.config_entries.flow.async_configure(
                        result["flow_id"], user_input={}
                    )
                )
            )
            authorization_release.set()
            first_result = await submissions[0]
            second_result = await submissions[1]
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            await hass.async_block_till_done()
            assert first_exchange.call_args_list + second_exchange.call_args_list == [
                call(expected_url)
            ]
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
            await hass.async_block_till_done(wait_background_tasks=True)
            assert first_exchange.call_args_list + second_exchange.call_args_list == [
                call(expected_url)
            ]
        finally:
            authorization_release.set()
            await asyncio.gather(*submissions, return_exceptions=True)
            await hass.async_block_till_done()

    assert first_result["type"] is first_type
    assert second_result["type"] is FlowResultType.EXTERNAL_STEP
    assert second_result["step_id"] == "auth_url"
    assert second_result["url"] == expected_url
    assert session_key_generator.call_count == expected_requests
    assert result["reason"] == "reauth_successful"
    assert authenticated_config_entry.options == {
        **CONF_DATA_WITH_SESSION_KEY,
        CONF_SESSION_KEY: NEW_SESSION_KEY,
    }
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    ("session_username", "session_error", "expected_reason"),
    [
        pytest.param(USERNAME_2, None, "wrong_account", id="wrong_account"),
        pytest.param(
            USERNAME_1,
            WSError("network", "15", "Token expired"),
            "auth_failed",
            id="expired_token",
        ),
    ],
)
async def test_reauth_flow_failure(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    mock_session_key_generator: MagicMock,
    session_username: str,
    session_error: Exception | None,
    expected_reason: str,
) -> None:
    """Test failed reauthentication preserves the entry options."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    session_exchange.return_value = SESSION_KEY, session_username
    session_exchange.side_effect = session_error
    authenticated_config_entry.add_to_hass(hass)
    result = await authenticated_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reauth_flow_start_retry(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test retrying a transient web authentication start failure."""
    mock_session_key_generator.get_web_auth_url.side_effect = WSError(
        "network", "16", "Service unavailable"
    )
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    session_exchange.return_value = NEW_SESSION_KEY, USERNAME_1
    authenticated_config_entry.add_to_hass(hass)
    with patch_setup_entry():
        result = await authenticated_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

        mock_session_key_generator.get_web_auth_url.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()
        session_exchange.assert_called_once_with(AUTH_URL)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert authenticated_config_entry.options == {
        **CONF_DATA_WITH_SESSION_KEY,
        CONF_SESSION_KEY: NEW_SESSION_KEY,
    }
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_flow_abort_cancels_session_key_polling(
    hass: HomeAssistant,
    default_user: MockUser,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test aborting the flow cancels session key polling."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()
        session_exchange.assert_not_called()

        hass.config_entries.flow.async_abort(result["flow_id"])
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_not_called()

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_flow_abort_prevents_queued_submit_session_exchange(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test a queued Submit does not exchange a session after the flow is aborted."""
    session_key_generator = MockSessionKeyGenerator()
    exchange_started = asyncio.Event()
    exchange_release = Event()
    submit_started = asyncio.Event()
    submissions: list[asyncio.Task[ConfigFlowResult]] = []

    def blocked_exchange(url: str, token: str = "") -> tuple[str, str]:
        """Wait for the flow to be aborted before returning a retryable error."""
        hass.loop.call_soon_threadsafe(exchange_started.set)
        assert exchange_release.wait(5)
        raise WSError("network", "16", "Service unavailable")

    async def queued_submit() -> ConfigFlowResult:
        """Signal when the second Submit starts."""
        submit_started.set()
        return await hass.config_entries.flow.async_configure(flow_id)

    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=session_key_generator),
        patch.object(
            session_key_generator,
            "get_web_auth_session_key_username",
            side_effect=blocked_exchange,
        ) as session_exchange,
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        flow_id = result["flow_id"]
        submissions.append(
            hass.async_create_task(hass.config_entries.flow.async_configure(flow_id))
        )
        try:
            await exchange_started.wait()
            submissions.append(hass.async_create_task(queued_submit()))
            await submit_started.wait()
            assert not submissions[1].done()
            session_exchange.assert_called_once_with(AUTH_URL)
            hass.config_entries.flow.async_abort(flow_id)
        finally:
            exchange_release.set()
            results = await asyncio.gather(*submissions, return_exceptions=True)
            await hass.async_block_till_done()

        assert isinstance(results[0], UnknownFlow)
        assert isinstance(results[1], UnknownFlow)
        session_exchange.assert_called_once_with(AUTH_URL)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_flow_abort_after_terminal_polling_error(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test aborting the flow before terminal polling advances it."""
    session_key_generator = MockSessionKeyGenerator(
        session_key_error=WSError("network", "15", "Token expired")
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=session_key_generator),
        patch.object(
            session_key_generator,
            "get_web_auth_session_key_username",
            wraps=session_key_generator.get_web_auth_session_key_username,
        ) as session_exchange,
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()

        advancement_started = asyncio.Event()
        release_advancement = asyncio.Event()
        async_configure = hass.config_entries.flow.async_configure

        async def delayed_configure(flow_id: str) -> ConfigFlowResult:
            """Pause the automatic transition until the flow is aborted."""
            advancement_started.set()
            await release_advancement.wait()
            return await async_configure(flow_id)

        with patch.object(
            hass.config_entries.flow, "async_configure", side_effect=delayed_configure
        ) as configure:
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
            try:
                await advancement_started.wait()
                session_exchange.assert_called_once_with(AUTH_URL)
                hass.config_entries.flow.async_abort(result["flow_id"])
            finally:
                release_advancement.set()
            await hass.async_block_till_done(wait_background_tasks=True)
            configure.assert_awaited_once_with(result["flow_id"])

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done(wait_background_tasks=True)
        session_exchange.assert_called_once_with(AUTH_URL)

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
    hass: HomeAssistant,
    error: Exception,
    message: str,
    default_user: MockUser,
    mock_session_key_generator: MagicMock,
) -> None:
    """Test user flow when starting web authentication fails."""
    mock_session_key_generator.get_web_auth_url.side_effect = error
    with patch("pylast.User", return_value=default_user):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == message

    mock_session_key_generator.get_web_auth_url.side_effect = None
    with (
        patch("pylast.User", return_value=default_user),
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
            WSError("network", 503, "Service unavailable"),
            id="http_service_unavailable",
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
    mock_session_key_generator: MagicMock,
) -> None:
    """Test the flow waits until the Last.fm authorization is granted."""
    session_exchange = mock_session_key_generator.get_web_auth_session_key_username
    session_exchange.side_effect = session_key_error
    with (
        patch("pylast.User", return_value=default_user),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth_url"

        session_exchange.side_effect = None
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
        pytest.param(PyLastError("Library failure"), "unknown", id="library_error"),
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
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["options"] == CONF_DATA


async def test_flow_hidden_recent_tracks(
    hass: HomeAssistant, default_user: MockUser
) -> None:
    """Test user initialized flow when user hides recent listening information."""
    with patch(
        "pylast.User",
        return_value=MockUser(recent_tracks_error=LOGIN_REQUIRED_ERROR),
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
        assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_session_key_generator")
async def test_flow_hidden_user_with_secret(hass: HomeAssistant) -> None:
    """Test a hidden user is accepted when an API secret is provided."""
    with (
        patch(
            "pylast.User",
            return_value=MockUser(recent_tracks_error=LOGIN_REQUIRED_ERROR),
        ),
        patch_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_USER_DATA_WITH_SECRET
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
            call(api_key=API_KEY),
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
        return_value=MockUser(recent_tracks_error=LOGIN_REQUIRED_ERROR),
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
