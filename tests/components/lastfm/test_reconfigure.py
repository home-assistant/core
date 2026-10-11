"""Test reconfiguring Last.fm credentials."""

from threading import Event
from unittest.mock import patch

from pylast import NetworkError, WSError
import pytest

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_ENABLE_AUTHENTICATION,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    API_KEY,
    API_SECRET,
    CONF_DATA,
    CONF_DATA_WITH_SESSION_KEY,
    NEW_SESSION_KEY,
    USERNAME_1,
    USERNAME_2,
    MockLastTrack,
    MockSessionKeyGenerator,
    MockUser,
    get_session_key_polling_task,
    patch_setup_entry,
)

from tests.common import MockConfigEntry

FLOW_MODULE = "homeassistant.components.lastfm.config_flow"
SESSION_KEY_GENERATOR_PATH = f"{FLOW_MODULE}.SessionKeyGenerator"
POLLING_INTERVAL_PATH = f"{FLOW_MODULE}.POLLING_INTERVAL"
NEW_API_KEY = "new-api-key"
NEW_API_SECRET = "new-api-secret"
RECONFIGURE_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_ENABLE_AUTHENTICATION: True,
    CONF_API_SECRET: API_SECRET,
}


class BlockingUser(MockUser):
    """Pause recent-tracks validation while another flow changes the entry."""

    def __init__(self) -> None:
        """Initialize validation events."""
        super().__init__()
        self.validation_started = Event()
        self.validation_release = Event()

    def get_recent_tracks(self, limit: int) -> list[MockLastTrack]:
        """Wait until reconfiguration has finished before returning tracks."""
        self.validation_started.set()
        assert self.validation_release.wait(5)
        return super().get_recent_tracks(limit)


class BlockingAccountUser(BlockingUser):
    """Pause account validation during reconfiguration."""

    def get_playcount(self) -> int:
        """Wait until the entry credentials change before finishing validation."""
        self.validation_started.set()
        assert self.validation_release.wait(5)
        return super().get_playcount()


@pytest.mark.parametrize(
    ("entry_fixture", "user_input", "session_username", "expected_options"),
    [
        pytest.param(
            "config_entry",
            RECONFIGURE_DATA,
            USERNAME_1,
            {**CONF_DATA_WITH_SESSION_KEY, CONF_SESSION_KEY: NEW_SESSION_KEY},
            id="enable",
        ),
        pytest.param(
            "imported_config_entry",
            {**RECONFIGURE_DATA, CONF_MAIN_USER: USERNAME_1},
            USERNAME_1,
            {**CONF_DATA_WITH_SESSION_KEY, CONF_SESSION_KEY: NEW_SESSION_KEY},
            id="imported_entry",
        ),
        pytest.param(
            "config_entry",
            RECONFIGURE_DATA,
            USERNAME_1.upper(),
            {**CONF_DATA_WITH_SESSION_KEY, CONF_SESSION_KEY: NEW_SESSION_KEY},
            id="account_case",
        ),
        pytest.param(
            "authenticated_config_entry",
            {**RECONFIGURE_DATA, CONF_API_SECRET: NEW_API_SECRET},
            USERNAME_1,
            {
                **CONF_DATA_WITH_SESSION_KEY,
                CONF_API_SECRET: NEW_API_SECRET,
                CONF_SESSION_KEY: NEW_SESSION_KEY,
            },
            id="replace_secret",
        ),
        pytest.param(
            "authenticated_config_entry",
            {
                **RECONFIGURE_DATA,
                CONF_API_KEY: NEW_API_KEY,
                CONF_API_SECRET: NEW_API_SECRET,
            },
            USERNAME_1,
            {
                **CONF_DATA_WITH_SESSION_KEY,
                CONF_API_KEY: NEW_API_KEY,
                CONF_API_SECRET: NEW_API_SECRET,
                CONF_SESSION_KEY: NEW_SESSION_KEY,
            },
            id="replace_api_account",
        ),
    ],
)
async def test_reconfigure_authorization(
    hass: HomeAssistant,
    hidden_user: MockUser,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    user_input: dict[str, str | bool],
    session_username: str,
    expected_options: dict[str, str | list[str]],
) -> None:
    """Authorize an existing hidden profile without creating another entry."""
    entry: MockConfigEntry = request.getfixturevalue(entry_fixture)
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    with (
        patch("pylast.User", return_value=hidden_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(
                session_key=NEW_SESSION_KEY, session_username=session_username
            ),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry() as setup_entry,
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert (CONF_MAIN_USER in result["data_schema"].schema) == (
            CONF_MAIN_USER in user_input
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert entry.options == original_options
        polling_task = get_session_key_polling_task(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
        assert result["step_id"] == "finish_reconfigure"
        assert entry.options == original_options
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.options == expected_options
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert polling_task.cancelled()
    setup_entry.assert_called_once_with(hass, entry)


@pytest.mark.parametrize(
    ("entry_fixture", "user_input", "expected_options"),
    [
        pytest.param(
            "authenticated_config_entry",
            {CONF_API_KEY: API_KEY, CONF_ENABLE_AUTHENTICATION: True},
            CONF_DATA_WITH_SESSION_KEY,
            id="keep_secret",
        ),
        pytest.param(
            "authenticated_config_entry",
            {**RECONFIGURE_DATA, CONF_API_SECRET: ""},
            CONF_DATA_WITH_SESSION_KEY,
            id="blank_secret",
        ),
        pytest.param(
            "authenticated_config_entry",
            {**RECONFIGURE_DATA, CONF_ENABLE_AUTHENTICATION: False},
            CONF_DATA,
            id="disable",
        ),
        pytest.param(
            "authenticated_config_entry",
            {CONF_API_KEY: NEW_API_KEY, CONF_ENABLE_AUTHENTICATION: False},
            {**CONF_DATA, CONF_API_KEY: NEW_API_KEY},
            id="disable_and_replace_key",
        ),
        pytest.param(
            "config_entry",
            {CONF_API_KEY: NEW_API_KEY, CONF_ENABLE_AUTHENTICATION: False},
            {**CONF_DATA, CONF_API_KEY: NEW_API_KEY},
            id="anonymous_key",
        ),
    ],
)
async def test_reconfigure_without_authorization(
    hass: HomeAssistant,
    hidden_user: MockUser,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    user_input: dict[str, str | bool],
    expected_options: dict[str, str | list[str]],
) -> None:
    """Keep the session or explicitly disable authentication for a hidden profile."""
    entry: MockConfigEntry = request.getfixturevalue(entry_fixture)
    entry.add_to_hass(hass)
    with (
        patch("pylast.User", return_value=hidden_user),
        patch(SESSION_KEY_GENERATOR_PATH) as session_key_generator,
        patch_setup_entry(),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.options == expected_options
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    session_key_generator.assert_not_called()


@pytest.mark.parametrize(
    ("entry_fixture", "user_input"),
    [
        pytest.param(
            "config_entry",
            {CONF_API_KEY: API_KEY, CONF_ENABLE_AUTHENTICATION: True},
            id="missing_secret",
        ),
        pytest.param(
            "config_entry",
            {**RECONFIGURE_DATA, CONF_API_SECRET: ""},
            id="empty_secret",
        ),
        pytest.param(
            "authenticated_config_entry",
            {CONF_API_KEY: NEW_API_KEY, CONF_ENABLE_AUTHENTICATION: True},
            id="new_key_requires_secret",
        ),
    ],
)
async def test_reconfigure_requires_matching_secret(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    user_input: dict[str, str | bool],
) -> None:
    """Do not pair a new API key with a missing or implicitly retained secret."""
    entry: MockConfigEntry = request.getfixturevalue(entry_fixture)
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    with patch(SESSION_KEY_GENERATOR_PATH) as session_key_generator:
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_SECRET: "api_secret_required"}
    assert entry.options == original_options
    session_key_generator.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(
            WSError("network", "10", "Invalid API key"),
            "invalid_auth",
            id="invalid_key",
        ),
        pytest.param(
            WSError("network", "16", "Service unavailable"),
            "cannot_connect",
            id="service_unavailable",
        ),
        pytest.param(
            NetworkError("network", Exception()), "cannot_connect", id="network"
        ),
    ],
)
async def test_reconfigure_authorization_start_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    default_user: MockUser,
    error: Exception,
    expected_error: str,
) -> None:
    """Keep the old configuration when starting authorization fails and retry."""
    config_entry.add_to_hass(hass)
    generator = MockSessionKeyGenerator(web_auth_url_error=error)
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=generator),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=RECONFIGURE_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}
        assert config_entry.options == CONF_DATA

        generator.web_auth_url_error = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=RECONFIGURE_DATA
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert config_entry.options == CONF_DATA_WITH_SESSION_KEY


@pytest.mark.parametrize(
    ("generator", "expected_reason"),
    [
        pytest.param(
            MockSessionKeyGenerator(session_username=USERNAME_2),
            "wrong_account",
            id="wrong_account",
        ),
        pytest.param(
            MockSessionKeyGenerator(
                session_key_error=WSError("network", "15", "Token expired")
            ),
            "auth_failed",
            id="expired_token",
        ),
        pytest.param(
            MockSessionKeyGenerator(session_key_error=Exception()),
            "auth_failed",
            id="unexpected_error",
        ),
    ],
)
async def test_reconfigure_authorization_failure(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    default_user: MockUser,
    generator: MockSessionKeyGenerator,
    expected_reason: str,
) -> None:
    """Failed credential replacement must preserve the working session."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=generator),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await authenticated_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_DATA, CONF_API_SECRET: NEW_API_SECRET},
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reconfigure_automatic_authorization(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hidden_user: MockUser,
) -> None:
    """Automatic authorization finishes reconfiguration instead of initial setup."""
    config_entry.add_to_hass(hass)
    with (
        patch("pylast.User", return_value=hidden_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 0),
        patch_setup_entry(),
    ):
        result = await config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=RECONFIGURE_DATA
        )
        await get_session_key_polling_task(hass, result["flow_id"])
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert config_entry.options == CONF_DATA_WITH_SESSION_KEY
    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]


async def test_reconfigure_abort(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Cancel polling and retain credentials when reconfiguration is abandoned."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await authenticated_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_DATA, CONF_API_SECRET: NEW_API_SECRET},
        )
        polling_task = get_session_key_polling_task(hass, result["flow_id"])
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    assert polling_task.cancelled()
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(SOURCE_REAUTH, id="reauth"),
        pytest.param(SOURCE_RECONFIGURE, id="reconfigure"),
    ],
)
async def test_reconfigure_rejects_concurrent_credentials_flow(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    source: str,
) -> None:
    """Only one credential flow may run for an entry at a time."""
    authenticated_config_entry.add_to_hass(hass)
    with (
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        pending = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": authenticated_config_entry.entry_id},
        )
        result = await authenticated_config_entry.start_reconfigure_flow(hass)
        hass.config_entries.flow.async_abort(pending["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    assert authenticated_config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reconfigure_preserves_users_changed_during_authorization(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """A users options save during authorization must survive credential updates."""
    config_entry.add_to_hass(hass)
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        result = await config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=RECONFIGURE_DATA
        )
        options_result = await hass.config_entries.options.async_init(
            config_entry.entry_id
        )
        options_result = await hass.config_entries.options.async_configure(
            options_result["flow_id"], user_input={CONF_USERS: [USERNAME_1]}
        )
        assert options_result["type"] is FlowResultType.CREATE_ENTRY
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert config_entry.options == {
        **CONF_DATA_WITH_SESSION_KEY,
        CONF_USERS: [USERNAME_1],
    }


async def test_options_save_cannot_restore_credentials_after_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Reject an options save validated with credentials replaced while it waited."""
    config_entry.add_to_hass(hass)
    user = BlockingUser()
    with (
        patch("pylast.User", return_value=default_user),
        patch(SESSION_KEY_GENERATOR_PATH, return_value=MockSessionKeyGenerator()),
        patch(POLLING_INTERVAL_PATH, 60),
        patch_setup_entry(),
    ):
        options_result = await hass.config_entries.options.async_init(
            config_entry.entry_id
        )
        result = await config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=RECONFIGURE_DATA
        )
        with patch("pylast.User", return_value=user):
            options_task = hass.async_create_task(
                hass.config_entries.options.async_configure(
                    options_result["flow_id"], user_input={CONF_USERS: [USERNAME_1]}
                )
            )
            try:
                assert await hass.async_add_executor_job(
                    user.validation_started.wait, 5
                )
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"]
                )
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"]
                )
            finally:
                user.validation_release.set()
            options_result = await options_task
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert options_result["type"] is FlowResultType.ABORT
    assert options_result["reason"] == "configuration_changed"
    assert config_entry.options == CONF_DATA_WITH_SESSION_KEY


async def test_reconfigure_rejects_credentials_changed_before_submit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Do not submit a credential form for a configuration that has changed."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    new_options = {**CONF_DATA, CONF_API_KEY: NEW_API_KEY}
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=RECONFIGURE_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_changed"
    assert config_entry.options == new_options


async def test_reconfigure_rejects_credentials_changed_during_validation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Reject stale validation before requesting an authorization token."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    user = BlockingAccountUser()
    new_options = {**CONF_DATA, CONF_API_KEY: NEW_API_KEY}
    with (
        patch("pylast.User", return_value=user),
        patch(SESSION_KEY_GENERATOR_PATH) as session_key_generator,
    ):
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=RECONFIGURE_DATA
            )
        )
        try:
            assert await hass.async_add_executor_job(user.validation_started.wait, 5)
            hass.config_entries.async_update_entry(config_entry, options=new_options)
        finally:
            user.validation_release.set()
        result = await task

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_changed"
    assert config_entry.options == new_options
    session_key_generator.assert_not_called()


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(SOURCE_REAUTH, id="reauth"),
        pytest.param(SOURCE_RECONFIGURE, id="reconfigure"),
    ],
)
async def test_authorization_rejects_credentials_changed_before_finish(
    hass: HomeAssistant,
    authenticated_config_entry: MockConfigEntry,
    default_user: MockUser,
    source: str,
) -> None:
    """An authorization result must not replace credentials changed during the flow."""
    authenticated_config_entry.add_to_hass(hass)
    new_options = {**CONF_DATA_WITH_SESSION_KEY, CONF_API_KEY: NEW_API_KEY}
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            SESSION_KEY_GENERATOR_PATH,
            return_value=MockSessionKeyGenerator(session_key=NEW_SESSION_KEY),
        ),
        patch(POLLING_INTERVAL_PATH, 60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": authenticated_config_entry.entry_id},
            data={**RECONFIGURE_DATA, CONF_API_SECRET: NEW_API_SECRET},
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        hass.config_entries.async_update_entry(
            authenticated_config_entry, options=new_options
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_changed"
    assert authenticated_config_entry.options == new_options
